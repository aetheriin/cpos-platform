"""Pengganti paket yang belum terpasang (pyodbc, dotenv, fastapi, pydantic) supaya uji bisa jalan tanpa SQL Server.
Kalau paketnya terpasang, yang asli dipakai."""
import os
import sys
import tempfile
import types


def _ada(nama):
    try:
        __import__(nama)
        return True
    except ImportError:
        return False


def pasang():
    # Log aktivitas dari uji (masuk, export, dst.) tidak boleh tercampur dengan log server sungguhan
    os.environ.setdefault("AKTIVITAS_FOLDER", tempfile.mkdtemp(prefix="uji_aktivitas_"))
    if not _ada("pyodbc"):
        m = types.ModuleType("pyodbc")
        m.connect = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("pyodbc palsu: tidak ada SQL Server di uji"))
        sys.modules["pyodbc"] = m
    if not _ada("dotenv"):
        sys.modules["dotenv"] = types.SimpleNamespace(load_dotenv=lambda *a, **k: None)
    if not _ada("fastapi"):
        class _App:
            def __init__(self, *a, **k): pass
            def add_middleware(self, *a, **k): pass
            def middleware(self, *a, **k): return lambda f: f
            def get(self, *a, **k): return lambda f: f
            def post(self, *a, **k): return lambda f: f
            def delete(self, *a, **k): return lambda f: f
            def put(self, *a, **k): return lambda f: f

        class HTTPException(Exception):
            def __init__(self, status_code, detail):
                self.status_code, self.detail = status_code, detail

        class Response:
            def __init__(self, content=None, media_type=None, headers=None, **k):
                self.cookies, self.dihapus = {}, []
                self.body, self.media_type, self.headers = content, media_type, dict(headers or {})

            def set_cookie(self, key, value, **k):
                self.cookies[key] = (value, k)

            def delete_cookie(self, key, **k):
                self.dihapus.append(key)

        fa = types.ModuleType("fastapi")
        fa.FastAPI, fa.Depends, fa.Query, fa.HTTPException = _App, (lambda f=None: f), (lambda *a, **k: None), HTTPException
        fa.Cookie, fa.Response = (lambda *a, **k: None), Response
        fa.Request = type("Request", (), {})
        mw, cors = types.ModuleType("fastapi.middleware"), types.ModuleType("fastapi.middleware.cors")
        cors.CORSMiddleware = object
        sys.modules.update({"fastapi": fa, "fastapi.middleware": mw, "fastapi.middleware.cors": cors})
    if not _ada("pydantic"):
        class BaseModel:
            def __init__(self, **k): self.__dict__.update(k)

        p = types.ModuleType("pydantic")
        p.BaseModel = BaseModel
        sys.modules["pydantic"] = p
