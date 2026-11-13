"""Mesin pencarian New Item Request: sama dengan aplikasi Item Similarity Search (Item/app.py) tanpa perubahan rumus.

Data item: EXEC dbo.all_company_items (Company, ItemCode, ItemName, Category); pembelian terakhir:
EXEC dbo.last_purchase_by_item @Company, @ItemCode. Skor = 45% semantik (sentence-transformers multibahasa) + 30% TF-IDF
+ 15% fuzzy token-set + 10% fuzzy token-sort; kategori ditebak dari 10 hasil teratas (bobot similarity kuadrat).

Bedanya dengan aplikasi aslinya hanya cara pakainya di CPOS:
- koneksi dari .env (ITEM_REQUEST_SERVER / _DB / _USER / _PASSWORD atau ITEM_REQUEST_CONNECTION_STRING), bukan
  password yang ditulis di kode;
- data & model dimuat di belakang (thread) saat halaman pertama kali dibuka, supaya CPOS tetap cepat menyala.
Library: pip install -r modules/item_request/requirements.txt (pandas, numpy, rapidfuzz, scikit-learn, sentence-transformers)."""
import logging
import os
import re
import threading

TOP_N = 10
LAST_PURCHASE_TOP = 4

MODEL_NAME = (
    "sentence-transformers/"
    "paraphrase-multilingual-MiniLM-L12-v2"
)

log = logging.getLogger(__name__)


# ===== koneksi (dari .env) =====
def get_connection():
    import pyodbc
    from utils.koneksi_lain import connection_string
    # database Main (dbo.all_company_items, dbo.last_purchase_by_item); server & akun DB_* kecuali ITEM_REQUEST_* diisi
    return pyodbc.connect(connection_string("ITEM_REQUEST", "CPOS-ItemRequest", db_bawaan="Main"), timeout=15)


# normalize

def normalize_text(text):

    text = str(text).lower()

    text = re.sub(
        r"[^a-z0-9\s]",
        " ",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    ).strip()

    return text


def attach_last_purchase(results, top_n=LAST_PURCHASE_TOP):

    # default: semua item belum punya last purchase
    for item in results:
        item["LastPurchase"] = None

    try:

        conn = get_connection()

        try:

            cursor = conn.cursor()

            for item in results[:top_n]:

                cursor.execute(
                    "EXEC dbo.last_purchase_by_item "
                    "@Company=?, @ItemCode=?",
                    item["COMP"],
                    item["ItemCode"]
                )

                rows = cursor.fetchall()

                if rows:
                    kolom = {
                        re.sub(r"[^a-z0-9]", "", str(deskripsi[0]).lower()): indeks
                        for indeks, deskripsi in enumerate(cursor.description or [])
                    }

                    def nilai(row, *nama):
                        for kandidat in nama:
                            indeks = kolom.get(re.sub(r"[^a-z0-9]", "", kandidat.lower()))
                            if indeks is not None:
                                return row[indeks]
                        return None

                    row = rows[0]
                    warehouse_rows = []
                    has_row_per_warehouse = any(
                        re.sub(r"[^a-z0-9]", "", name.lower()) in kolom
                        for name in (
                            "WarehouseName",
                            "WarehouseDescription",
                            "WarehouseBalance",
                            "BalancePerWarehouse",
                        )
                    )

                    if has_row_per_warehouse:
                        for warehouse_row in rows:
                            warehouse_name = nilai(
                                warehouse_row, "WarehouseName", "WarehouseDescription"
                            )
                            warehouse_code = nilai(
                                warehouse_row, "WarehouseCode", "Warehouse"
                            )
                            warehouse_balance = nilai(
                                warehouse_row, "WarehouseBalance", "BalancePerWarehouse"
                            )
                            if warehouse_name is not None or warehouse_code is not None or warehouse_balance is not None:
                                warehouse_rows.append({
                                    "Name": warehouse_name or warehouse_code,
                                    "Code": warehouse_code,
                                    "Balance": warehouse_balance,
                                })
                    else:
                        kolom_ringkasan = {
                            "company",
                            "itemcode",
                            "itemname",
                            "purchaseno",
                            "purchasedate",
                            "supplierid",
                            "suppliername",
                            "supplier",
                            "qty",
                            "cost",
                            "price",
                            "totalbalance",
                        }
                        warehouse_rows = [
                            {
                                "Name": str(deskripsi[0]),
                                "Code": None,
                                "Balance": row[indeks],
                            }
                            for indeks, deskripsi in enumerate(cursor.description or [])
                            if re.sub(r"[^a-z0-9]", "", str(deskripsi[0]).lower())
                            not in kolom_ringkasan
                            and row[indeks] is not None
                        ]

                    if not warehouse_rows:
                        log.warning(
                            "Kolom/hasil warehouse tidak ditemukan dari dbo.last_purchase_by_item; kolom tersedia: %s",
                            list(kolom),
                        )

                    item["LastPurchase"] = {
                        "PurchaseNo": nilai(row, "PurchaseNo"),
                        "PurchaseDate": nilai(row, "PurchaseDate"),
                        "Qty": nilai(row, "Qty"),
                        "Price": nilai(row, "Cost", "Price"),
                        "SupplierName": nilai(row, "SupplierName", "Supplier"),
                        "Warehouses": warehouse_rows,
                        "TotalBalance": nilai(row, "TotalBalance"),
                    }

        finally:

            conn.close()

    except Exception as e:

        # kalau gagal, pencarian utama tetap jalan
        log.warning("ERROR last purchase: %s", e)

    return results


# load data
def load_data_sql():
    import pandas as pd

    log.info("Item Request: memuat data item (EXEC dbo.all_company_items)")

    conn = get_connection()

    try:

        df = pd.read_sql(
            "EXEC dbo.all_company_items",
            conn
        )

    finally:

        conn.close()


    # column

    df = df.rename(
        columns={
            "Company": "COMP"
        }
    )


    # check

    required_columns = [
        "COMP",
        "ItemCode",
        "ItemName",
        "Category"
    ]


    missing = [
        column
        for column in required_columns
        if column not in df.columns
    ]


    if missing:

        raise ValueError(
            "Kolom berikut tidak ditemukan "
            f"dari Stored Procedure: {missing}"
        )


    df = df[
        required_columns
    ].copy()


    # cleaning

    for column in required_columns:

        df[column] = (
            df[column]
            .fillna("")
            .astype(str)
            .str.strip()
        )


    # search

    df["SearchText"] = (
        df["ItemName"]
        .apply(normalize_text)
    )


    # remove empty item name

    df = df[
        df["SearchText"].str.len() > 0
    ].reset_index(drop=True)


    log.info("Item Request: %s item dimuat", f"{len(df):,}")

    return df


# nlp
class ItemNLP:

    def __init__(
        self,
        dataframe
    ):
        from sentence_transformers import SentenceTransformer
        from sklearn.feature_extraction.text import TfidfVectorizer

        self.df = dataframe


        # tf idf

        self.vectorizer = TfidfVectorizer(

            analyzer="word",

            ngram_range=(1, 2),

            sublinear_tf=True,

            min_df=1
        )


        self.matrix = (
            self.vectorizer
            .fit_transform(
                self.df["SearchText"]
            )
        )


        # sentence transformer

        self.semantic_model = (
            SentenceTransformer(
                MODEL_NAME
            )
        )


        # semantic embedding

        self.semantic_matrix = (
            self.semantic_model.encode(

                self.df[
                    "ItemName"
                ].tolist(),

                batch_size=64,

                show_progress_bar=False,

                convert_to_numpy=True,

                normalize_embeddings=True
            )
        )


    # search

    def search(
        self,
        query,
        top_n=10,
        company=None
    ):
        import numpy as np
        import pandas as pd
        from rapidfuzz import fuzz
        from sklearn.metrics.pairwise import cosine_similarity

        # normalize
        query_clean = normalize_text(
            query
        )


        if not query_clean:

            return pd.DataFrame()


        # comp filter

        if (
            company
            and
            company != "SEMUA"
        ):

            indexes = np.where(

                self.df[
                    "COMP"
                ]
                .str.upper()
                .values

                ==

                company.upper()

            )[0]

        else:

            indexes = np.arange(
                len(self.df)
            )


        if len(indexes) == 0:

            return pd.DataFrame()


        # tf idf

        query_vector = (
            self.vectorizer
            .transform(
                [query_clean]
            )
        )


        tfidf_scores = (
            cosine_similarity(

                query_vector,

                self.matrix[
                    indexes
                ]

            )
            .flatten()
        )


        # fuzzy

        fuzzy_scores = []


        query_token_count = max(
            len(
                query_clean.split()
            ),
            1
        )


        for i in indexes:

            item_text = (
                self.df
                .iloc[i][
                    "SearchText"
                ]
            )


            item_token_count = max(
                len(
                    item_text.split()
                ),
                1
            )


            length_factor = min(

                1.0,

                item_token_count
                /
                query_token_count
            )


            score = (

                fuzz.token_set_ratio(

                    query_clean,

                    item_text

                )
                /
                100.0

            ) * length_factor


            fuzzy_scores.append(
                score
            )


        fuzzy_scores = np.array(
            fuzzy_scores
        )


        # score

        sort_scores = np.array([

            fuzz.token_sort_ratio(

                query_clean,

                self.df
                .iloc[i][
                    "SearchText"
                ]

            )
            /
            100.0

            for i in indexes

        ])


        # semantic

        query_embedding = (
            self.semantic_model.encode(

                query,

                convert_to_numpy=True,

                normalize_embeddings=True
            )
        )


        query_embedding = (
            query_embedding
            .reshape(
                1,
                -1
            )
        )


        semantic_scores = (
            cosine_similarity(

                query_embedding,

                self.semantic_matrix[
                    indexes
                ]

            )
            .flatten()
        )


        # clip

        semantic_scores = np.clip(

            semantic_scores,

            0,

            1
        )


        # hybrid

        final_scores = (

            0.45 * semantic_scores

            +

            0.30 * tfidf_scores

            +

            0.15 * fuzzy_scores

            +

            0.10 * sort_scores

        )


        # rank

        order = np.argsort(
            -final_scores
        )[:top_n]


        result_indexes = (
            indexes[
                order
            ]
        )


        # result

        result = (

            self.df
            .iloc[
                result_indexes
            ]

            [
                [
                    "COMP",
                    "ItemCode",
                    "ItemName",
                    "Category"
                ]
            ]

            .copy()
        )


        # similarity

        result.insert(

            0,

            "Similarity",

            (
                final_scores[
                    order
                ]
                *
                100
            ).round(2)

        )


        return (
            result
            .reset_index(
                drop=True
            )
        )


    # predict

    def predict_category(

        self,

        query,

        company=None,

        top_n=10

    ):

        results = self.search(

            query=query,

            top_n=top_n,

            company=company
        )


        if results.empty:

            return None


        category_scores = {}


        for _, row in results.iterrows():

            category = str(
                row["Category"]
            ).strip()


            if not category:

                continue


            score = float(
                row["Similarity"]
            )


            # Semakin tinggi similarity,
            # semakin besar pengaruhnya

            weight = max(
                score,
                0.01
            ) ** 2


            category_scores[
                category
            ] = (

                category_scores.get(
                    category,
                    0
                )

                +

                weight

            )


        if not category_scores:

            return None


        return max(

            category_scores,

            key=category_scores.get
        )


# ===== pemuatan di belakang (CPOS) =====
_kunci = threading.Lock()          # satu pencarian dalam satu waktu (model & matriks dipakai bersama)
PESAN_GAGAL = "Data item belum bisa dimuat. Coba lagi nanti, atau hubungi IT."
_status = {"keadaan": "BELUM", "pesan": "", "engine": None, "companies": []}


def status():
    """BELUM / MEMUAT / SIAP / GAGAL + pesan (untuk halaman)."""
    return {"keadaan": _status["keadaan"], "pesan": _status["pesan"], "companies": _status["companies"]}


def _muat():
    try:
        df = load_data_sql()
        engine = ItemNLP(df)
        companies = sorted(df["COMP"].dropna().astype(str).unique().tolist())
        _status.update(engine=engine, companies=companies, keadaan="SIAP",
                       pesan=f"{len(df):,} item dimuat".replace(",", "."))
    except ImportError as e:
        log.error("Item Request: library %s belum terpasang. Jalankan: pip install -r modules/item_request/requirements.txt", e.name)
        _status.update(keadaan="GAGAL", pesan=PESAN_GAGAL)
    except Exception:           # noqa: BLE001 - penyebab teknis ke log, pengguna mendapat pesan umum
        log.exception("Item Request gagal dimuat")
        _status.update(keadaan="GAGAL", pesan=PESAN_GAGAL)


def mulai_muat(ulang=False):
    """Mulai memuat data & model di thread (sekali; ulang=True setelah GAGAL)."""
    with _kunci:
        if _status["keadaan"] == "MEMUAT" or (_status["keadaan"] == "SIAP" and not ulang) \
                or (_status["keadaan"] == "GAGAL" and not ulang):
            return
        _status.update(keadaan="MEMUAT", pesan="Memuat data item & model (bisa 1 - 2 menit)...")
    threading.Thread(target=_muat, name="item-request-muat", daemon=True).start()


def cari(query, company="SEMUA"):
    """Sama dengan route index() aplikasi asli: hasil (10 teratas, 4 teratas dengan pembelian terakhir) + kategori."""
    engine = _status["engine"]
    if engine is None:
        raise RuntimeError("Data item belum siap")
    with _kunci:
        result_df = engine.search(query=query, top_n=TOP_N, company=company)
        if result_df.empty:
            return [], None
        results = attach_last_purchase(result_df.to_dict(orient="records"))
        category = engine.predict_category(query=query, company=company, top_n=TOP_N)
    return results, category
