import cv2
import numpy as np
import onnxruntime as ort
import os

# ID COCO untuk target: 2=Mobil, 3=Motor, 5=Bus, 7=Truk
KELAS_TARGET = {2: "Mobil", 3: "Motor", 5: "Bus", 7: "Truk"}


class DetektorKendaraan:
    def __init__(self, model_path="yolox_s.onnx"):
        if not os.path.exists(model_path):
            print(f"Peringatan: {model_path} tidak ditemukan. Klasifikasi jenis kendaraan dinonaktifkan.")
            self.sesi = None
            return

        try:
            self.sesi = ort.InferenceSession(model_path, providers=['CPUExecutionProvider'])
            self.input_name = self.sesi.get_inputs()[0].name
            self.grids, self.strides = self._buat_grid((640, 640))
            print(f"Model YOLOX ({model_path}) berhasil dimuat.")
        except Exception as e:
            print(f"Gagal memuat YOLOX ONNX: {e}")
            self.sesi = None

    def _buat_grid(self, input_shape):
        grids, strides = [], []
        for stride in [8, 16, 32]:
            hsize, wsize = input_shape[0] // stride, input_shape[1] // stride
            yv, xv = np.meshgrid(np.arange(hsize), np.arange(wsize), indexing='ij')
            grid = np.stack((xv, yv), 2).reshape(1, -1, 2)
            grids.append(grid)
            strides.append(np.full((1, grid.shape[1], 1), stride))
        return np.concatenate(grids, 1), np.concatenate(strides, 1)

    def praproses(self, img, input_size=(640, 640)):
        h, w = img.shape[:2]
        r = min(input_size[0] / h, input_size[1] / w)
        resize_w, resize_h = int(w * r), int(h * r)

        img_resize = cv2.resize(img, (resize_w, resize_h), interpolation=cv2.INTER_LINEAR)
        padded = np.ones((input_size[0], input_size[1], 3), dtype=np.uint8) * 114
        padded[:resize_h, :resize_w] = img_resize

        padded = padded.transpose((2, 0, 1))
        padded = np.ascontiguousarray(padded, dtype=np.float32)
        return padded, r

    def deteksi(self, frame):
        if not self.sesi:
            return "Unknown"

        try:
            img, r = self.praproses(frame)
            out = self.sesi.run(None, {self.input_name: img[None, ...]})[0][0]

            out[:, :2] = (out[:, :2] + self.grids[0]) * self.strides[0]
            out[:, 2:4] = np.exp(out[:, 2:4]) * self.strides[0]
            out[:, :4] /= r

            kotak = out[:, :4]
            skor_objek = out[:, 4]
            skor_kelas = out[:, 5:]

            id_kelas = np.argmax(skor_kelas, axis=1)
            skor_final = skor_objek * skor_kelas[np.arange(len(skor_kelas)), id_kelas]

            valid = (skor_final > 0.45) & np.isin(id_kelas, list(KELAS_TARGET.keys()))
            if not np.any(valid):
                return "Unknown"

            kotak_valid, skor_valid, id_valid = kotak[valid], skor_final[valid], id_kelas[valid]

            xywh = kotak_valid.copy()
            xywh[:, 0] -= xywh[:, 2] / 2
            xywh[:, 1] -= xywh[:, 3] / 2

            indices = cv2.dnn.NMSBoxes(xywh.tolist(), skor_valid.tolist(), 0.45, 0.45)
            if len(indices) == 0:
                return "Unknown"

            indices = np.array(indices).flatten()
            terbaik_idx, luas_terbesar = indices[0], 0

            for i in indices:
                luas = kotak_valid[i, 2] * kotak_valid[i, 3]
                if luas > luas_terbesar:
                    luas_terbesar = luas
                    terbaik_idx = i

            return KELAS_TARGET[id_valid[terbaik_idx]]
        except Exception as e:
            print(f"Error deteksi YOLOX: {e}")
            return "Unknown"
