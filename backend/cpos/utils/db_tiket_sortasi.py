"""Penyimpanan hasil Sortasi pada tiket Ascend."""

from datetime import datetime
from decimal import Decimal

from utils.db_tiket_common import koneksi_tiket as _koneksi

def simpan_hasil_sortasi_tiket(
    no_tiket,
    deduction_kg=None,
    mentah=None,
    busuk=None,
    tangkai=None,
    sampah=None,
    matang=None,
    brondolan=None,
    operator=None,
):
    """Simpan Deduction dan grading langsung pada tiket."""
    no_tiket = (no_tiket or "").strip()
    operator_login = str(operator or "").strip()[:30]

    if not no_tiket:
        raise ValueError("Nomor tiket wajib diisi.")
    if not operator_login:
        raise ValueError("Petugas Sortasi wajib diisi.")

    def angka_opsional(nilai, nama, persen=False):
        if nilai is None or str(nilai).strip() == "":
            return None
        try:
            hasil = Decimal(str(nilai))
        except Exception as exc:
            raise ValueError(f"Nilai {nama} harus berupa angka.") from exc
        if not hasil.is_finite() or hasil < 0:
            raise ValueError(f"Nilai {nama} tidak valid.")
        if persen and hasil > 100:
            raise ValueError(f"Nilai {nama} harus antara 0 dan 100.")
        return hasil

    deduction = angka_opsional(deduction_kg, "Deduction")
    grading = {
        "unripe": angka_opsional(mentah, "buah mentah", persen=True),
        "rotton": angka_opsional(busuk, "buah busuk", persen=True),
        "longstalk": angka_opsional(tangkai, "tangkai panjang", persen=True),
        "rubbish": angka_opsional(sampah, "sampah", persen=True),
        "gradingmasak": angka_opsional(matang, "buah matang", persen=True),
        "brondolan": angka_opsional(brondolan, "brondolan", persen=True),
    }

    if deduction is None and not any(v is not None for v in grading.values()):
        raise ValueError("Isi Deduction atau minimal satu nilai grading.")

    koneksi = _koneksi()
    try:
        cursor = koneksi.cursor()
        cursor.execute(
            """
            SELECT TOP (1) *
            FROM dbo.PALM_Tickets WITH (UPDLOCK, HOLDLOCK)
            WHERE TicketNo = ?
              AND ISNULL(Void, 0) = 0
              AND ISNULL(Pemisahanted, 0) = 0
            ORDER BY TicketID DESC
            """,
            no_tiket,
        )
        row = cursor.fetchone()
        if not row:
            raise ValueError("Tiket Tiket tidak ditemukan atau sudah selesai.")

        kolom = [item[0] for item in cursor.description]
        tiket = {nama.casefold(): row[i] for i, nama in enumerate(kolom)}

        if (
            str(tiket.get("tickettype") or "").strip() != "TBSLuar"
            or str(tiket.get("productname") or "").strip().casefold() != "tbs"
        ):
            raise ValueError("Sortasi hanya berlaku untuk tiket TBS Luar produk TBS.")

        if int(tiket.get("step") or 0) != 1:
            raise ValueError("Sortasi hanya dapat disimpan setelah timbang pertama dan sebelum timbang akhir.")

        for nama, nilai in grading.items():
            if nilai is not None:
                tiket[nama] = nilai

        if deduction is not None:
            tiket["deduction"] = deduction

        if any(v is not None for v in grading.values()):
            tiket["gradingperformed"] = 1

        sekarang = datetime.now()
        tiket["sortasiby"] = operator_login[:50]
        tiket["sortasidatetime"] = sekarang

        bruto = Decimal(str(tiket.get("bruto") or 0))
        tara = Decimal(str(tiket.get("tara") or 0))
        deduction_tersimpan = Decimal(str(tiket.get("deduction") or 0))
        timbang3 = Decimal(str(tiket.get("timbang3") or 0))
        tara_netto = timbang3 if timbang3 > 0 else tara

        cursor.execute(
            """
            SELECT dbo.UDF_SH_Settings_GetAsBit(
                'PALM_Tickets.IncludeKgRejectInNetto', 0
            )
            """
        )
        include_kg_reject = bool(cursor.fetchone()[0])
        kg_reject = (
            Decimal(str(tiket.get("kgreject") or 0))
            if include_kg_reject else Decimal("0")
        )

        # CheckNetto Tiket: Bruto - Tara/Timbang3 - Deduction + KgReject.
        tiket["netto"] = bruto - tara_netto - deduction_tersimpan + kg_reject

        cursor.execute(
            """
            SELECT name
            FROM sys.parameters
            WHERE object_id = OBJECT_ID('dbo.USP_PALM_Tickets_Update')
              AND parameter_id > 0
            ORDER BY parameter_id
            """
        )
        nama_parameter = [r[0] for r in cursor.fetchall()]

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
                nilai = tiket.get("operator") or operator_login
            elif kunci == "savelab":
                nilai = 0
            elif kunci == "sortasistr":
                nilai = ""
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
                "Data tiket tidak cukup untuk update Sortasi: "
                + ", ".join(tidak_tersedia)
            )

        sql = (
            "EXEC dbo.USP_PALM_Tickets_Update "
            + ", ".join(f"{nama} = ?" for nama in parameter_terisi)
        )
        cursor.execute(sql, *nilai_parameter)

        cursor.execute(
            """
            SELECT Deduction, Netto, Unripe, Rotton, LongStalk,
                   Rubbish, GradingMasak, Brondolan
            FROM dbo.PALM_Tickets
            WHERE TicketID = ?
            """,
            int(tiket["ticketid"]),
        )
        tersimpan = cursor.fetchone()
        if not tersimpan:
            raise RuntimeError("Hasil Sortasi tidak ditemukan saat membaca balik Tiket.")

        deduction_db, netto_db, *grading_db = tersimpan
        harapan_deduction = Decimal(str(tiket.get("deduction") or 0))

        if (
            deduction_db is None
            or abs(Decimal(str(deduction_db)) - harapan_deduction)
            > Decimal("0.01")
        ):
            raise RuntimeError("Deduction yang tersimpan di Tiket tidak sesuai.")

        netto_harapan = Decimal(str(tiket.get("netto") or 0))
        if (
            netto_db is None
            or abs(Decimal(str(netto_db)) - netto_harapan) > Decimal("0.01")
        ):
            raise RuntimeError("Netto hasil update Sortasi tidak sesuai.")
        
        harapan_grading = [
            tiket.get("unripe"),
            tiket.get("rotton"),
            tiket.get("longstalk"),
            tiket.get("rubbish"),
            tiket.get("gradingmasak"),
            tiket.get("brondolan"),
        ]
        for nilai_db, harapan in zip(grading_db, harapan_grading):
            if harapan is not None and (
                nilai_db is None
                or abs(Decimal(str(nilai_db)) - Decimal(str(harapan)))
                > Decimal("0.01")
            ):
                raise RuntimeError("Nilai grading yang tersimpan di Tiket tidak sesuai.")

        koneksi.commit()
        return {
            "ticket_id": int(tiket["ticketid"]),
            "ticket_no": no_tiket,
            "deduction_kg": float(deduction_db or 0),
            "netto": float(netto_db or 0),
        }
    except Exception:
        koneksi.rollback()
        raise
    finally:
        koneksi.close()