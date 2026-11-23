"""Penyimpanan hasil Lab pada tiket Ascend."""

from decimal import Decimal

from utils.db_tiket_common import koneksi_tiket as _koneksi

def simpan_hasil_lab_tiket( no_tiket, ffa=None, suhu=None,
    ulage=None, pct_air=None, pct_kotoran=None, kcolor=None, operator=None,
):
    """Simpan pengukuran Lab pada tiket induk Tiket lewat USP_PALM_Tickets_Update."""
    no_tiket = (no_tiket or "").strip()
    if not no_tiket:
        raise ValueError("Nomor tiket wajib diisi.")

    def angka_opsional(nilai, nama, batas_persen=False):
        if nilai is None or str(nilai).strip() == "":
            return None
        try:
            hasil = Decimal(str(nilai))
        except Exception as exc:
            raise ValueError(f"Nilai {nama} harus berupa angka.") from exc
        if not hasil.is_finite() or hasil < 0:
            raise ValueError(f"Nilai {nama} tidak valid.")
        if batas_persen and hasil > 100:
            raise ValueError(f"Nilai {nama} harus antara 0 dan 100.")
        return hasil

    ffa = angka_opsional(ffa, "FFA", batas_persen=True)
    suhu = angka_opsional(suhu, "suhu")
    ulage = angka_opsional(ulage, "Ulage")
    pct_air = angka_opsional(pct_air, "kadar air", batas_persen=True)
    pct_kotoran = angka_opsional(pct_kotoran, "kadar kotoran", batas_persen=True)

    warna = (kcolor or "").strip()[:30] or None
    operator_login = str(operator or "").strip()[:30]
    if not operator_login:
        raise ValueError("Petugas Lab wajib diisi.")

    koneksi = _koneksi()
    try:
        cursor = koneksi.cursor()

        cursor.execute(
            """
            SELECT TOP (1) *
            FROM dbo.PALM_Tickets WITH (UPDLOCK, HOLDLOCK)
            WHERE TicketNo = ?
              AND ISNULL(Void, 0) = 0
            ORDER BY TicketID DESC
            """,
            no_tiket,
        )
        row = cursor.fetchone()
        if not row:
            raise ValueError("Tiket Tiket tidak ditemukan atau sudah dibatalkan.")

        kolom = [item[0] for item in cursor.description]
        tiket = {nama.casefold(): row[i] for i, nama in enumerate(kolom)}

        # Hasil satu muatan pisah disimpan sekali pada tiket induk.
        parent_id = int(tiket.get("parentticketid") or 0)
        if parent_id:
            cursor.execute(
                """
                SELECT *
                FROM dbo.PALM_Tickets WITH (UPDLOCK, HOLDLOCK)
                WHERE TicketID = ?
                  AND ISNULL(Void, 0) = 0
                """,
                parent_id,
            )
            row_induk = cursor.fetchone()
            if not row_induk:
                raise ValueError("Tiket induk Tiket untuk hasil Lab tidak ditemukan.")
            kolom = [item[0] for item in cursor.description]
            tiket = {nama.casefold(): row_induk[i] for i, nama in enumerate(kolom)}

        jenis = str(tiket.get("tickettype") or "").strip()
        produk = str(tiket.get("productname") or "").strip().upper()

        if jenis != "Produk" or produk not in {"CPO", "PK", "KERNEL"}:
            raise ValueError("Lab Tiket saat ini hanya menerima produk CPO, PK, dan Kernel.")

        # Ubah hanya hasil Lab yang dikirim; nilai timbang, DO, dan field tiket lain dipertahankan.
        for kunci, nilai in (
            ("ffa", ffa),
            ("suhu", suhu),
            ("ulage", ulage),
            ("pctair", pct_air),
            ("pctkotoran", pct_kotoran),
            ("kcolor", warna),
        ):
            if nilai is not None:
                tiket[kunci] = nilai

        tiket["savelab"] = 1

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

            if kunci == "loginname":
                nilai = operator_login
            elif kunci == "operator":
                # Pertahankan operator tiket yang sudah tercatat.
                nilai = tiket.get("operator") or operator_login
            elif kunci == "savelab":
                nilai = 1
            elif kunci == "spdo2":
                nilai = ""
            elif kunci in {"linktodo", "force", "checkmaxdolimit"}:
                nilai = 0
            elif kunci in tiket:
                nilai = tiket[kunci]
            else:
                if kunci in wajib:
                    tidak_tersedia.append(nama)
                continue

            parameter_terisi.append(nama)
            nilai_parameter.append(nilai)

        if tidak_tersedia:
            raise RuntimeError(
                "Data tiket tidak cukup untuk menyimpan hasil Lab: "
                + ", ".join(tidak_tersedia)
            )

        sql = (
            "EXEC dbo.USP_PALM_Tickets_Update "
            + ", ".join(f"{nama} = ?" for nama in parameter_terisi)
        )
        cursor.execute(sql, *nilai_parameter)

        ticket_id = int(tiket["ticketid"])
        cursor.execute(
            """
            SELECT FFA, Suhu, Ulage, PctAir, PctKotoran, KColor, LabBy, LabDateTime
            FROM dbo.PALM_Tickets
            WHERE TicketID = ?
            """,
            ticket_id,
        )
        tersimpan = cursor.fetchone()
        if not tersimpan:
            raise RuntimeError("Hasil Lab tidak ditemukan saat membaca balik tiket.")

        ffa_db, suhu_db, ulage_db, air_db, kotoran_db, warna_db, lab_by_db, lab_at_db = tersimpan

        for nama, nilai_db, harapan in (
            ("FFA", ffa_db, ffa),
            ("suhu", suhu_db, suhu),
            ("Ulage", ulage_db, ulage),
            ("kadar air", air_db, pct_air),
            ("kadar kotoran", kotoran_db, pct_kotoran),
        ):
            if harapan is not None and (
                nilai_db is None
                or abs(Decimal(str(nilai_db)) - harapan) > Decimal("0.01")
            ):
                raise RuntimeError(f"Nilai {nama} yang tersimpan di Tiket tidak sesuai.")

        if warna is not None and str(warna_db or "").strip() != warna:
            raise RuntimeError("Warna yang tersimpan di Tiket tidak sesuai.")
        if not lab_by_db or lab_at_db is None:
            raise RuntimeError("Audit petugas/waktu Lab belum tersimpan di Tiket.")

        koneksi.commit()
        return {
            "ticket_id": ticket_id,
            "ticket_no": str(tiket.get("ticketno") or "").strip(),
            "ticket_type": jenis,
            "product": produk,
            "lab_by": str(lab_by_db).strip(),
            "lab_datetime": lab_at_db,
            "ffa": float(ffa_db) if ffa_db is not None else None,
            "suhu": float(suhu_db) if suhu_db is not None else None,
            "ulage": float(ulage_db) if ulage_db is not None else None,
            "pct_air": float(air_db) if air_db is not None else None,
            "pct_kotoran": float(kotoran_db) if kotoran_db is not None else None,
            "kcolor": str(warna_db or "").strip(),
        }
    except Exception:
        koneksi.rollback()
        raise
    finally:
        koneksi.close()