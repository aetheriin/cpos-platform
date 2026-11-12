import os
import re

from extensions import BASE_DIR
from utils.cache import cache_ttl


@cache_ttl(60)
def versi_aplikasi():
    try:
        with open(os.path.join(BASE_DIR, "VERSION"), encoding="utf-8") as f:
            teks = f.read().strip()
    except OSError:
        return "-"
    return re.sub(r"^(cpos)?\s*v?\s*", "", teks, flags=re.I) or "-"
