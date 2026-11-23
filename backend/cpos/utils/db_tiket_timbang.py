"""Pembacaan dan penyimpanan timbang tiket Ascend."""

from datetime import datetime
from decimal import Decimal

from utils import db_tiket_pisah
from utils.db_tiket_common import koneksi_tiket as _koneksi
from utils.db_tiket_kontrak_do import (
    _baca_do_produk_tiket,
    cari_pasangan_do2_tiket,
)

def baca_berat_tiket(no_tiket):
    """Baca berat Tiket sesuai tahap timbang tiket."""
    koneksi = _koneksi()
    try:
        cursor = koneksi.cursor()
        cursor.execute(
            """
            SELECT TOP (1) Bruto, Tara, Netto, TicketType, [Step]
            FROM dbo.PALM_Tickets
            WHERE TicketNo = ?
              AND ISNULL([Void], 0) = 0
              AND ISNULL([Pemisahanted], 0) = 0
            ORDER BY TicketID DESC
            """,
            no_tiket,
        )
        row = cursor.fetchone()

        if not row:
            return None

        bruto, tara, netto, ticket_type, step = row
        step = int(step or 0)

        # Tiket kosong: nilai 0 di database belum berarti sudah timbang.
        if step <= 0:
            bruto = tara = netto = None
        elif step == 1:
            # Produk/penjualan: timbang pertama adalah Tara.
            if ticket_type == "Produk":
                bruto = None
                netto = None
            # TBS Luar/penerimaan: timbang pertama adalah Bruto.
            else:
                tara = None
                netto = None

        return {
            "berat_bruto": float(bruto) if bruto is not None else None,
            "berat_tara": float(tara) if tara is not None else None,
            "berat_netto": float(netto) if netto is not None else None,
        }
    finally:
        koneksi.close()

def baca_hasil_pisah_tiket(ticket_id):
    koneksi = _koneksi()
    try:
        cursor = koneksi.cursor()
        cursor.execute(
            """
            SELECT SPDO, [Step], DateTimeOut, Pemisahanted, Void
            FROM dbo.PALM_Tickets
            WHERE TicketID = ?
            """,
            int(ticket_id),
        )
        induk = cursor.fetchone()
        if not induk:
            return None

        cursor.execute(
            """
            SELECT TicketID, TicketNo, SPDO, Netto, [Step]
            FROM dbo.PALM_Tickets
            WHERE ParentTicketID = ?
              AND ISNULL([Void], 0) = 0
            ORDER BY TicketID
            """,
            int(ticket_id),
        )
        anak = [
            {
                "ticket_id": int(row[0]),
                "no_tiket": str(row[1] or "").strip(),
                "no_do": str(row[2] or "").strip(),
                "berat_netto": float(row[3] or 0),
                "step": int(row[4] or 0),
            }
            for row in cursor.fetchall()
        ]

        return {
            "no_do1": str(induk[0] or "").strip(),
            "step": int(induk[1] or 0),
            "datetimeout": induk[2],
            "pisahted": bool(induk[3]),
            "void": bool(induk[4]),
            "anak": anak,
        }
    finally:
        koneksi.close()

def simpan_berat_tiket(no_tiket, berat_kg, operator, waktu_timbang=None):
    """Simpan timbang ke Tiket melalui USP_PALM_Tickets_Update."""
    koneksi = _koneksi()
    try:
        cursor = koneksi.cursor()

        # Kunci baris sampai transaksi selesai agar timbang tidak tersimpan ganda.
        cursor.execute(
            """
            SELECT TOP (1) *
            FROM dbo.PALM_Tickets WITH (UPDLOCK, HOLDLOCK)
            WHERE TicketNo = ?
              AND ISNULL([Void], 0) = 0
              AND ISNULL([Pemisahanted], 0) = 0
              AND (ISNULL([Step], 0) < 2 OR DateTimeOut IS NULL)
            ORDER BY TicketID DESC
            """,
            no_tiket,
        )
        row = cursor.fetchone()
        if not row:
            raise ValueError("Tiket Tiket tidak ditemukan atau sudah selesai.")

        kolom = [item[0] for item in cursor.description]
        tiket = {nama.casefold(): row[i] for i, nama in enumerate(kolom)}

        def nilai(nama, default=None):
            return tiket.get(nama.casefold(), default)

        step = int(nilai("Step", 0) or 0)
        ticket_type = str(nilai("TicketType", "") or "").strip()
        berat = Decimal(str(berat_kg))

        if berat <= 0:
            raise ValueError("Berat timbang harus lebih dari 0 kg.")
        if step not in (0, 1):
            raise ValueError("Tiket ini tidak berada pada tahap timbang yang bisa disimpan.")

        bruto = Decimal(str(nilai("Bruto", 0) or 0))
        tara = Decimal(str(nilai("Tara", 0) or 0))
        now = waktu_timbang or datetime.now()
        spdo2 = ""
        deduction_harapan = None

        if step == 0:
            if ticket_type == "Produk":
                tara = berat
                tiket["taradatetime"] = now
                tiket["taraby"] = str(operator)[:50]
            elif ticket_type == "TBSLuar":
                bruto = berat
                tiket["brutoby"] = str(operator)[:50]
            else:
                raise ValueError(f"Jenis tiket {ticket_type!r} belum didukung.")

            step_baru = 1
            date_time_out = nilai("DateTimeOut")

        else:  # Step 1: simpan timbang terakhir
            if ticket_type == "Produk":
                bruto = berat
                tiket["brutoby"] = str(operator)[:50]
            elif ticket_type == "TBSLuar":
                tara = berat
                tiket["taradatetime"] = now
                tiket["taraby"] = str(operator)[:50]
            else:
                raise ValueError(f"Jenis tiket {ticket_type!r} belum didukung.")

            if bruto <= tara:
                raise ValueError("Bruto harus lebih besar daripada Tara.")

            step_baru = 2
            date_time_out = now
            tiket["netto"] = bruto - tara

            nama_produk = str(nilai("ProductName", "") or "").strip().casefold()
            if ticket_type == "TBSLuar" and nama_produk == "tbs":
                deduction_harapan = Decimal(
                    str(nilai("Deduction", 0) or 0)
                )

                cursor.execute(
                    """
                    SELECT dbo.UDF_SH_Settings_GetAsBit(
                        'PALM_Tickets.IncludeKgRejectInNetto', 0
                    )
                    """
                )
                include_kg_reject = bool(cursor.fetchone()[0])
                kg_reject = (
                    Decimal(str(nilai("KgReject", 0) or 0))
                    if include_kg_reject else Decimal("0")
                )

                timbang3 = Decimal(str(nilai("Timbang3", 0) or 0))
                tara_untuk_netto = timbang3 if timbang3 > 0 else tara

                tiket["deduction"] = deduction_harapan
                tiket["netto"] = (
                    bruto
                    - tara_untuk_netto
                    - deduction_harapan
                    + kg_reject
                )

        tiket["bruto"] = bruto
        tiket["tara"] = tara
        tiket["step"] = step_baru
        tiket["datetimeout"] = date_time_out

        if step_baru == 2 and ticket_type == "Produk":
            no_do1 = str(nilai("SPDO", "") or "").strip()
            alasan_pending = None

            try:
                do1 = _baca_do_produk_tiket(no_do1)
            except Exception as e:
                do1 = None
                alasan_pending = (
                    f"Data DO pertama Tiket belum dapat dibaca: {e}"
                )

            if not alasan_pending:
                if not do1:
                    alasan_pending = (
                        "DO pertama tidak ditemukan di Tiket; "
                        "menunggu data DO dapat dipastikan."
                    )
                elif do1["void"]:
                    raise ValueError(
                        "DO pertama sudah dibatalkan di Tiket. "
                        "Tiket perlu diperiksa sebelum timbang akhir disimpan."
                    )
                else:
                    netto_final = Decimal(str(tiket["netto"]))
                    sisa_do1 = Decimal(str(do1["sisa"] or 0))

                    # DO yang ditutup tidak menerima alokasi baru.
                    if do1["closed"]:
                        sisa_do1 = Decimal("0")

                    if netto_final > sisa_do1:
                        try:
                            do2 = cari_pasangan_do2_tiket(
                                "Produk",
                                no_do1,
                            )
                        except Exception as e:
                            do2 = None
                            alasan_pending = (
                                f"Pasangan DO2 belum dapat dipastikan: {e}"
                            )

                        if not alasan_pending:
                            if not do2:
                                alasan_pending = (
                                    "Netto melewati sisa DO1; "
                                    "menunggu DO2 yang cocok."
                                )
                            elif sisa_do1 > 0:
                                # Masih ada bagian untuk DO1: minta Tiket pisah.
                                spdo2 = do2["no_do"]
                            else:
                                # DO1 habis: seluruh tiket diarahkan ke DO2.
                                # Tidak meminta Tiket membuat anak dengan netto 0.
                                tiket["spdo"] = do2["no_do"]
                                tiket["deliveryorderid"] = int(do2["id_do"])

            if alasan_pending:
                pending = db_tiket_pisah.simpan_timbang_akhir_pending(
                    int(nilai("TicketID")),
                    berat,
                    now,
                    int(operator),
                    alasan_pending,
                )

                koneksi.rollback()
                return {
                    "step": 2,
                    "ticket_type": ticket_type,
                    "ticket_id": int(nilai("TicketID")),
                    "ticket_no": no_tiket,
                    "pending_do2": True,
                    "pending_status": pending["status"],
                    "no_do2": None,
                    "tiket_pisah": [],
                    "berat_bruto": float(bruto),
                    "berat_tara": float(tara),
                    "berat_netto": float(bruto - tara),
                }

        # Ambil parameter prosedur Tiket; kirim nilai yang tersedia di baris tiket.
        cursor.execute(
            """
            SELECT name
            FROM sys.parameters
            WHERE object_id = OBJECT_ID('dbo.USP_PALM_Tickets_Update')
              AND parameter_id > 0
            ORDER BY parameter_id
            """
        )
        nama_parameter = [row[0] for row in cursor.fetchall()]

        wajib = {
            "ticketid", "ticketno", "tickettype", "date", "datetimein",
            "estateid", "vehicleno", "referenceno", "associateid",
            "productname", "bruto", "tara", "deduction", "netto",
            "checkedby", "operator", "printcount", "step",
            "owncar", "allocated", "external",
        }

        parameter_terisi = []
        nilai_parameter = []
        tidak_tersedia = []

        for nama in nama_parameter:
            kunci = nama.lstrip("@").casefold()

            if kunci == "operator":
                isi = str(operator)[:50]
            elif kunci == "spdo2":
                isi = spdo2
            elif kunci == "loginname":
                isi = str(operator)[:30]
            elif kunci in tiket:
                isi = tiket[kunci]
            else:
                if kunci in wajib:
                    tidak_tersedia.append(nama)
                continue

            parameter_terisi.append(nama)
            nilai_parameter.append(isi)

        if tidak_tersedia:
            raise RuntimeError(
                "Kolom tiket tidak cukup untuk mengisi parameter wajib Tiket: "
                + ", ".join(tidak_tersedia)
            )

        sql = (
            "EXEC dbo.USP_PALM_Tickets_Update "
            + ", ".join(f"{nama} = ?" for nama in parameter_terisi)
        )
        cursor.execute(sql, *nilai_parameter)
        ticket_id_induk = int(nilai("TicketID"))
        tiket_pisah = []

        # Untuk timbang biasa, pastikan nilai benar-benar sudah tertulis
        # di PALM_Tickets sebelum transaksi di-commit.
        # Kasus pisah diperiksa lewat validasi dua tiket pecahan di bawah.
        if not spdo2:
            cursor.execute(
                """
                SELECT Bruto, Tara, Netto, [Step], DateTimeOut, SPDO, Deduction
                FROM dbo.PALM_Tickets
                WHERE TicketID = ?
                """,
                ticket_id_induk,
            )
            tersimpan = cursor.fetchone()

            if not tersimpan:
                raise RuntimeError(
                    "Tiket tidak ditemukan saat memeriksa hasil simpan timbang."
                )

            (
                bruto_db,
                tara_db,
                netto_db,
                step_db,
                datetime_out_db,
                spdo_db,
                deduction_db,
            ) = tersimpan
            toleransi_kg = Decimal("0.01")

            def berat_sesuai(nilai_db, nilai_harapan):
                if nilai_db is None:
                    return False
                return (
                    abs(Decimal(str(nilai_db)) - Decimal(str(nilai_harapan)))
                    <= toleransi_kg
                )

            if int(step_db or 0) != step_baru:
                raise RuntimeError(
                    "Step tiket tidak sama dengan tahap timbang yang dikirim."
                )

            if not berat_sesuai(bruto_db, bruto):
                raise RuntimeError(
                    "Nilai Bruto yang tersimpan di Tiket tidak sesuai."
                )

            if not berat_sesuai(tara_db, tara):
                raise RuntimeError(
                    "Nilai Tara yang tersimpan di Tiket tidak sesuai."
                )

            if step_baru == 2:
                netto_harapan = Decimal(str(tiket["netto"] or 0))

                if not berat_sesuai(netto_db, netto_harapan):
                    raise RuntimeError(
                        "Nilai Netto yang tersimpan di Tiket tidak sesuai."
                    )

                if deduction_harapan is not None:
                    if not berat_sesuai(deduction_db, deduction_harapan):
                        raise RuntimeError(
                            "Nilai Deduction yang tersimpan di Tiket tidak sesuai."
                        )

                if datetime_out_db is None:
                    raise RuntimeError(
                        "DateTimeOut belum tersimpan pada timbang terakhir."
                    )

            if ticket_type == "Produk" and step_baru == 2 and not spdo2:
                spdo_harapan = str(tiket.get("spdo") or "").strip()
                spdo_tersimpan = str(spdo_db or "").strip()

                if spdo_tersimpan.casefold() != spdo_harapan.casefold():
                    raise RuntimeError(
                        "Nomor DO tiket yang tersimpan di Tiket tidak sesuai."
                    )

        if spdo2:
            cursor.execute(
                """
                SELECT TicketID, TicketNo, SPDO, Netto, [Step]
                FROM dbo.PALM_Tickets
                WHERE ParentTicketID = ?
                  AND ISNULL([Void], 0) = 0
                ORDER BY TicketID
                """,
                ticket_id_induk,
            )

            tiket_pisah = [
                {
                    "ticket_id": int(row[0]),
                    "no_tiket": str(row[1] or "").strip(),
                    "no_do": str(row[2] or "").strip(),
                    "berat_netto": float(row[3] or 0),
                    "step": int(row[4] or 0),
                }
                for row in cursor.fetchall()
            ]

            if len(tiket_pisah) != 2:
                raise RuntimeError(
                    "Tiket menerima permintaan pisah, tetapi tidak "
                    "mengembalikan tepat dua tiket pecahan."
                )

            do_pecahan = {
                baris["no_do"].casefold()
                for baris in tiket_pisah
            }
            if do_pecahan != {
                str(nilai("SPDO", "") or "").strip().casefold(),
                spdo2.strip().casefold(),
            }:
                raise RuntimeError(
                    "DO pada tiket pecahan Tiket tidak cocok dengan DO1 dan DO2."
                )

            netto_pecahan = sum(
                Decimal(str(baris["berat_netto"]))
                for baris in tiket_pisah
            )
            netto_awal = Decimal(str(tiket["netto"] or 0))

            if abs(netto_pecahan - netto_awal) > Decimal("0.01"):
                raise RuntimeError(
                    "Jumlah netto tiket pecahan tidak sama dengan netto truk."
                )
        koneksi.commit()

        return {
            "step": step_baru,
            "ticket_type": ticket_type,
            "ticket_id": int(nilai("TicketID")),
            "ticket_no": no_tiket,
            "no_do2": spdo2 or None,
            "tiket_pisah": tiket_pisah,
            "berat_bruto": float(bruto) if step_baru == 2 or ticket_type == "TBSLuar" else None,
            "berat_tara": float(tara) if step_baru == 2 or ticket_type == "Produk" else None,
            "berat_netto": float(tiket["netto"]) if step_baru == 2 else None,
        }

    except Exception:
        koneksi.rollback()
        raise
    finally:
        koneksi.close()


