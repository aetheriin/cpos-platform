"""Pembaca kalimat Asisten: kalimat bebas -> permintaan terstruktur (ukuran, pemecah, saringan, periode).

Tanpa AI: kata dicocokkan ke kamus (kamus.py) dengan toleransi salah ketik, waktu dibaca dengan pola, sisanya dianggap nama yang dicari
(mis. nama supplier). Kalimat lanjutan ("kalau YBS?", "per supplier") melengkapi permintaan sebelumnya."""
import re
from datetime import date, timedelta
from difflib import SequenceMatcher

from . import kamus

_GAUL = {
    "yg": "yang", "blm": "belum", "blum": "belum", "sdh": "sudah", "udh": "sudah", "udah": "sudah", "dah": "sudah", "brp": "berapa",
    "brapa": "berapa", "bln": "bulan", "mgg": "minggu", "thn": "tahun", "th": "tahun", "dg": "dengan", "dgn": "dengan", "utk": "untuk",
    "tdk": "tidak", "gak": "tidak", "ga": "tidak", "nggak": "tidak", "krn": "karena", "jml": "jumlah", "tgl": "tanggal", "spl": "supplier",
    "hr": "hari", "kmrn": "kemarin", "skrg": "sekarang", "sy": "saya", "tlg": "tolong", "gmn": "gimana", "bgmn": "bagaimana",
    "trbesar": "terbesar", "terbsr": "terbesar", "plg": "paling", "pling": "paling", "dr": "dari", "sm": "sama", "smp": "sampai",
    "sd": "sampai", "s/d": "sampai", "vs": "banding", "versus": "banding", "dibanding": "banding", "dibandingkan": "banding",
    "bandingkan": "banding", "dibandingin": "banding", "bandingin": "banding", "ketimbang": "banding",
}
_BUANG = set("""yang di ke dari untuk berapa berapakah apa apakah saja ada total dengan dan atau ini itu kita kami saya tolong mohon lihat lihatkan
tampilkan tunjukkan tunjukan berikan kasih sih ya dong deh nih adalah per tiap setiap berdasarkan by data semua sekarang saat posisi bagaimana gimana
punya milik oleh pada dalam terhadap jumlahnya totalnya mau ingin tahu cek check cari carikan please the of masih sudah belum jadi kalau kalo terus
lalu bagaimana gimana dengan nya kah lah buat bikin minta coba jumlah nilai banyak berapa lagi juga hanya cuma cuman aja doang dong
paling sampai hingga antara mulai sejak selama
hai halo hallo pagi siang sore malam selamat permisi pak bu kak mas mbak bang bro""".split())
_BULAN = {"januari": 1, "februari": 2, "maret": 3, "april": 4, "mei": 5, "juni": 6, "juli": 7, "agustus": 8, "september": 9, "oktober": 10,
          "november": 11, "desember": 12}
_BULAN_PENDEK = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "agu": 8, "agt": 8, "agus": 8, "sep": 9, "sept": 9, "okt": 10,
                 "nov": 11, "des": 12}
_ANGKA = {"satu": 1, "dua": 2, "tiga": 3, "empat": 4, "lima": 5, "enam": 6, "tujuh": 7, "delapan": 8, "sembilan": 9, "sepuluh": 10,
          "lima belas": 15, "dua puluh": 20, "tiga puluh": 30, "lima puluh": 50}
NAMA_BULAN = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"]
_NOMOR = re.compile(r"\b[A-Z0-9]{2,8}(?:/[A-Z0-9.\-]{1,12}){2,6}\b|\b\d{4}-\d{4,6}\b", re.I)


def normal(teks):
    t = teks.casefold().replace("s/d", " sampai ")
    t = re.sub(r"[^\w\s\-]", " ", t)
    t = re.sub(r"(?<=[a-z])-(?=[a-z])", " ", t)   # "rata-rata" = "rata rata"
    hasil = []
    for k in t.split():
        k = _GAUL.get(k, k)
        if len(k) > 6 and k.endswith("nya") and k[:-3] not in _BUANG:
            k = k[:-3]
        hasil.append(k)
    return " ".join(hasil)


def _mirip(a, b):
    """Satu kata: sama persis untuk kata pendek; selainnya boleh beda sedikit (salah ketik)."""
    if a == b:
        return True
    if len(b) <= 3 or len(a) <= 3:
        return False
    return SequenceMatcher(None, a, b).ratio() >= 0.8


def _frasa():
    """[(jenis, kunci, [kata])] semua kata yang dikenali, dari kamus."""
    hasil = []
    for k, u in kamus.UKURAN.items():
        hasil += [("ukuran", k, s.split()) for s in u["sebutan"]]
    for k, p in kamus.PEMECAH.items():
        hasil += [("pemecah", k, s.split()) for s in p["sebutan"]]
    for i, s in enumerate(kamus.STATUS):
        hasil += [("status", i, x.split()) for x in s["sebutan"]]
    tanda = {
        "daftar": ["daftar", "list", "mana saja", "apa saja", "rincian", "detail", "detil", "dokumennya", "yang mana", "tabel"],
        "besar": ["terbesar", "paling besar", "tertinggi", "paling tinggi", "terbanyak", "paling banyak", "teratas", "top", "besar"],
        "kecil": ["terkecil", "paling kecil", "terendah", "paling rendah", "paling sedikit", "tersedikit"],
        "lama": ["terlama", "paling lama", "tertua", "paling tua", "paling lambat", "terlambat", "lama"],
        "baru": ["terbaru", "paling baru", "terakhir dibuat"],
        "banding": ["banding"],
        "siapa": ["siapa"],
        "mana": ["mana"],
        "semua_pt": ["semua perusahaan", "semua pt", "seluruh perusahaan", "gabungan"],
    }
    for k, daftar in tanda.items():
        hasil += [("tanda", k, s.split()) for s in daftar]
    return sorted(hasil, key=lambda x: -len(x[2]))


_FRASA = _frasa()


def _cocokkan(kata, terpakai):
    """Frasa terpanjang dulu; tiap kata hanya dipakai satu frasa. -> [(jenis, kunci, awal, panjang)]"""
    hasil = []
    for sama in (lambda a, b: a == b, _mirip):   # yang persis dulu, baru yang mirip ("piutang" bukan salah ketik "utang")
        for jenis, kunci, f in _FRASA:
            n = len(f)
            for i in range(len(kata) - n + 1):
                if any(terpakai[i:i + n]):
                    continue
                if all(sama(kata[i + j], f[j]) for j in range(n)):
                    hasil.append((jenis, kunci, i, n))
                    for j in range(i, i + n):
                        terpakai[j] = True
    return sorted(hasil, key=lambda x: x[2])


def _akhir_bulan(th, bl):
    return (date(th + (bl == 12), bl % 12 + 1, 1) - timedelta(days=1))


def _periode_bulan(th, bl, label=None):
    return {"dari": date(th, bl, 1).isoformat(), "sampai": _akhir_bulan(th, bl).isoformat(), "label": label or f"{NAMA_BULAN[bl - 1]} {th}"}


def _waktu(t, hari_ini):
    """Cari semua periode di kalimat. -> (teks tanpa bagian waktu, [periode])"""
    ketemu = []

    def simpan(m, p):
        ketemu.append((m.start(), p))
        return " " * (m.end() - m.start())

    h = hari_ini
    senin = h - timedelta(days=h.weekday())
    pola = [
        (r"\b(\d{1,3})\s+(hari|minggu|bulan)\s+(terakhir|belakangan|kebelakang|ke belakang)\b", lambda m: (
            lambda n, s: {"dari": (h - timedelta(days=n * {"hari": 1, "minggu": 7, "bulan": 30}[s] - 1)).isoformat(), "sampai": h.isoformat(),
                          "label": f"{n} {s} terakhir"})(int(m.group(1)), m.group(2))),
        (r"\bhari ini\b", lambda m: {"dari": h.isoformat(), "sampai": h.isoformat(), "label": "hari ini"}),
        (r"\bkemarin\b", lambda m: {"dari": (h - timedelta(days=1)).isoformat(), "sampai": (h - timedelta(days=1)).isoformat(), "label": "kemarin"}),
        (r"\bminggu (ini|sekarang)\b", lambda m: {"dari": senin.isoformat(), "sampai": h.isoformat(), "label": "minggu ini"}),
        (r"\bminggu (lalu|kemarin|sebelumnya)\b", lambda m: {"dari": (senin - timedelta(days=7)).isoformat(),
                                                             "sampai": (senin - timedelta(days=1)).isoformat(), "label": "minggu lalu"}),
        (r"\bbulan (ini|sekarang)\b", lambda m: {**_periode_bulan(h.year, h.month), "sampai": h.isoformat(), "label": "bulan ini"}),
        (r"\bbulan (lalu|kemarin|sebelumnya)\b", lambda m: {**_periode_bulan(*((h.year - 1, 12) if h.month == 1 else (h.year, h.month - 1))),
                                                            "label": "bulan lalu"}),
        (r"\b(tahun ini|ytd|awal tahun)\b", lambda m: {"dari": date(h.year, 1, 1).isoformat(), "sampai": h.isoformat(), "label": "tahun ini"}),
        (r"\btahun (lalu|kemarin)\b", lambda m: {"dari": date(h.year - 1, 1, 1).isoformat(), "sampai": date(h.year - 1, 12, 31).isoformat(),
                                                 "label": f"tahun {h.year - 1}"}),
    ]
    for p, buat in pola:
        t = re.sub(p, lambda m, buat=buat: simpan(m, buat(m)), t)

    def bulan(m):
        nama, th = m.group(2), m.group(3)
        bl = _BULAN.get(nama) or _BULAN_PENDEK.get(nama)
        if nama in _BULAN_PENDEK and not th and not m.group(1):
            return m.group(0)   # singkatan tanpa tahun dan tanpa kata "bulan" bisa jadi bagian nama
        tahun = int(th) if th else (h.year if bl <= h.month else h.year - 1)
        return simpan(m, _periode_bulan(tahun, bl))

    semua = "|".join(sorted(list(_BULAN) + list(_BULAN_PENDEK), key=len, reverse=True))
    t = re.sub(rf"\b(bulan\s+)?({semua})\b(?:\s+(20\d\d))?", bulan, t)
    t = re.sub(r"\b(tahun\s+)?(20\d\d)\b", lambda m: simpan(m, {"dari": f"{m.group(2)}-01-01", "sampai": min(date(int(m.group(2)), 12, 31), h).isoformat(),
                                                             "label": f"tahun {m.group(2)}"}), t)
    ketemu.sort(key=lambda x: x[0])
    periode = [p for _, p in ketemu]
    # "dari Agustus sampai Oktober": satu rentang
    if len(periode) == 2 and re.search(r"\b(sampai|hingga|ke|-)\b", t) and not re.search(r"\bbanding\b", t):
        periode = [{"dari": periode[0]["dari"], "sampai": periode[1]["sampai"], "label": f"{periode[0]['label']} sampai {periode[1]['label']}"}]
    return t, periode


def _angka_n(t):
    m = re.search(r"\b(?:top\s*)?(\d{1,3})\b", t)
    if m:
        return int(m.group(1)), t[:m.start()] + " " * (m.end() - m.start()) + t[m.end():]
    for kata, n in sorted(_ANGKA.items(), key=lambda x: -len(x[0])):
        m = re.search(rf"\b{kata}\b", t)
        if m:
            return n, t[:m.start()] + " " * (m.end() - m.start()) + t[m.end():]
    return None, t


_ISTILAH = re.compile(r"^(apa\s+(itu|arti|artinya|maksud|maksudnya|yang dimaksud)|arti|artinya|maksud|maksudnya|pengertian|definisi|jelaskan|"
                      r"apa sih)\b|\b(itu apa|artinya apa|apa artinya|maksudnya apa|"
                      r"(gimana|bagaimana|gmn)?\s*cara\s+(hitung|menghitung|ngitung|itung)(nya)?|"
                      r"(gimana|bagaimana) (hitung|ngitung|menghitung)(nya)?|dihitung (dari mana|bagaimana|gimana|pakai apa)|"
                      r"rumus(nya)?|asal angka(nya)?)\b")
_BANTU = re.compile(r"^(bantuan|help|tolong|bisa apa|kamu bisa apa|apa yang bisa|contoh|menu|panduan)\b|\bbisa (tanya|ditanya) apa\b")


def baca(teks, perusahaan_dikenal, hari_ini=None, menu=None):
    """-> permintaan (dict). perusahaan_dikenal: kode perusahaan (huruf besar). menu: id laporan yang sedang dibuka; kata yang artinya
    beda per menu ("belum", "belum pvr") dibaca menurut menu itu."""
    info_menu = kamus.MENU.get(menu or "", {})
    hari_ini = hari_ini or date.today()
    asli = teks.strip()
    p = {"maksud": None, "ukuran": None, "pemecah": None, "perusahaan": None, "status": [], "periode": None, "banding": None,
         "urut": None, "n": None, "cari": None, "nomor": None, "istilah": None, "lanjutan": False}
    nomor = _NOMOR.findall(asli)
    t = normal(asli)
    if nomor:
        p.update(maksud="dokumen", nomor=nomor[0].upper())
        return p
    if len(t.split()) <= 7:
        for i, o in enumerate(kamus.OBROLAN):
            if re.search(o["pola"], t):
                p.update(maksud="obrolan", obrolan=i)
                return p
    if re.search(kamus.POLA_MENU, t):
        p["maksud"] = "menu"
        return p
    if re.search(kamus.POLA_INSIGHT, t):
        kode = {k.casefold(): k for k in perusahaan_dikenal}
        p.update(maksud="insight", perusahaan=[kode[k] for k in t.split() if k in kode] or None)
        return p
    if _BANTU.search(t):
        p["maksud"] = "bantuan"
        return p
    if _ISTILAH.search(t):
        p["maksud"] = "istilah"
        p["istilah"] = _ISTILAH.sub(" ", t).strip()
        return p

    t, periode = _waktu(t, hari_ini)
    n, t = _angka_n(t)
    kata = t.split()
    kode = {k.casefold(): k for k in perusahaan_dikenal}
    pt = [kode[k] for k in kata if k in kode]
    terpakai = [k in kode for k in kata]
    cocok = _cocokkan(kata, terpakai)

    # Kata umum di menu ini ("yang belum" di menu PR = belum PO) kalau status belum disebut lengkap
    if info_menu.get("umum") and not any(c[0] == "status" for c in cocok):
        for i, k in enumerate(kata):
            frasa = info_menu["umum"].get(k)
            if frasa and not terpakai[i]:
                j = next((j for j, st in enumerate(kamus.STATUS) if frasa in st["sebutan"]
                          and st.get("sumber") in (None, info_menu.get("sumber"))), None)
                if j is not None:
                    cocok.append(("status", j, i, 1))
                    terpakai[i] = True
                    break
        cocok.sort(key=lambda x: x[2])

    tanda = set()
    for jenis, kunci, i, _ in cocok:
        if jenis == "ukuran" and p["ukuran"] is None:
            p["ukuran"] = kunci
        elif jenis == "pemecah" and p["pemecah"] is None:
            p["pemecah"] = kunci
        elif jenis == "status":
            p["status"].append(kunci)
        elif jenis == "tanda":
            tanda.add(kunci)
            if kunci in ("siapa", "mana") and i > 0:
                # "supplier mana": pemecah tepat sebelum kata tanya
                sebelum = [c for c in cocok if c[2] + c[3] == i and c[0] == "pemecah"]
                if sebelum:
                    tanda.add("pemecah_tanya")
    # Sebutan status yang sama di beberapa laporan ("belum pvr" untuk hutang dan PI): ikut ukuran yang disebut, lalu menu yang dibuka
    tujuan = kamus.UKURAN[p["ukuran"]]["sumber"] if p["ukuran"] else info_menu.get("sumber")
    if tujuan:
        for n_, i in enumerate(p["status"]):
            st = kamus.STATUS[i]
            if st.get("sumber") and st["sumber"] != tujuan:
                lain = next((j for j, x in enumerate(kamus.STATUS) if x.get("sumber") == tujuan and set(x["sebutan"]) & set(st["sebutan"])), None)
                if lain is not None:
                    p["status"][n_] = lain
    p["menu"] = menu
    if pt:
        p["perusahaan"] = sorted(set(pt))
    if "semua_pt" in tanda:
        p["perusahaan"] = []
    for u in ("besar", "kecil", "lama", "baru"):
        if u in tanda:
            p["urut"] = u
            break
    if "siapa" in tanda and not p["pemecah"]:
        p["pemecah"] = "siapa"   # diisi pengolah menurut ukurannya (supplier, customer, buyer, pembuat)
    if ("daftar" in tanda or ("mana" in tanda and "pemecah_tanya" not in tanda)) and not p["pemecah"]:
        p["maksud"] = "daftar"
    if ("pemecah_tanya" in tanda or "siapa" in tanda) and not p["urut"]:
        p["urut"] = "besar"
    if p["urut"] == "lama" and not p["pemecah"]:
        p["maksud"] = "daftar"
    if "banding" in tanda:
        p["banding"] = True
    p["n"] = n
    if periode:
        p["periode"] = periode[0]
        if len(periode) > 1:
            p["banding"] = True
            p["periode_banding"] = periode[1]

    sisa = [k for k, dipakai in zip(kata, terpakai) if not dipakai and k not in _BUANG and len(k) >= 3 and not k.isdigit()]
    if sisa:
        p["cari"] = " ".join(sisa)
    # tidak ada satu pun yang dikenali selain kata sisa: kalau kata itu juga tidak ada di data, kalimatnya tidak dipahami
    p["hanya_cari"] = not (cocok or pt or periode or n)
    # Kalimat pendek tanpa ukuran, atau yang dibuka "kalau/gimana dengan": lanjutan dari pertanyaan sebelumnya
    awal = normal(asli).split()[:1]
    p["lanjutan"] = bool(awal and awal[0] in ("kalau", "gimana", "bagaimana", "terus", "lalu", "yang", "kalo", "trus", "sedangkan", "untuk", "dan"))
    if p["maksud"] is None:
        p["maksud"] = "angka"
    return p


def lengkapi(p, lalu):
    """Permintaan lanjutan mengambil bagian yang tidak disebut dari permintaan sebelumnya (dari layar)."""
    if not lalu or p["maksud"] not in ("angka", "daftar") or lalu.get("maksud") not in ("angka", "daftar"):
        return p
    ada_isi = p["ukuran"] or p["status"]
    if ada_isi and not p["lanjutan"]:
        # pertanyaan baru dengan ukuran sendiri: perusahaan dan periode ikut hanya kalau kalimatnya pendek ("piutangnya?")
        if p["pemecah"] is None and p["perusahaan"] is None and p["periode"] is None and p["cari"] is None and p["maksud"] == "angka":
            p["perusahaan"], p["periode"] = lalu.get("perusahaan"), lalu.get("periode")
            p["pemecah"] = lalu.get("pemecah") if p["ukuran"] and kamus.UKURAN[p["ukuran"]]["sumber"] == kamus.UKURAN.get(lalu.get("ukuran") or "", {}).get("sumber") else None
            p["diwarisi"] = True
        return p
    hasil = dict(lalu)
    for k in ("ukuran", "pemecah", "perusahaan", "periode", "urut", "n", "banding", "periode_banding", "cari"):
        if p.get(k) not in (None, []) or (k == "perusahaan" and p.get(k) == []):
            hasil[k] = p[k]
    if p["status"]:
        hasil["status"] = p["status"]
    if p["pemecah"] and p["maksud"] != "daftar":
        hasil["maksud"] = "angka"
    elif p["maksud"] == "daftar":
        hasil["maksud"], hasil["pemecah"] = "daftar", None
        hasil["n"], hasil["urut"] = p.get("n"), p.get("urut") or (lalu.get("urut") if lalu.get("maksud") == "daftar" else None)
    hasil["diwarisi"] = True
    hasil["lanjutan"] = False
    hasil["hanya_cari"] = p.get("hanya_cari")
    return hasil
