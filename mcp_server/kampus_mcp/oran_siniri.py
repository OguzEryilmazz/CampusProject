"""Basit sabit pencereli oran sınırlayıcı (bellekte, tek süreç)."""
import time


class SabitPencere:
    def __init__(self, pencere_sn: int = 60, saat=time.monotonic, max_anahtar: int = 5000):
        self.pencere_sn = pencere_sn
        self._saat = saat
        self._max = max_anahtar
        self._kayit: dict[str, tuple[float, int]] = {}  # anahtar -> (pencere başı, sayaç)

    def _temizle(self, simdi: float):
        if len(self._kayit) > self._max:
            for k in [k for k, (b, _) in self._kayit.items() if simdi - b >= self.pencere_sn]:
                del self._kayit[k]

    def _guncel(self, anahtar: str, simdi: float) -> tuple[float, int]:
        bas, sayac = self._kayit.get(anahtar, (simdi, 0))
        if simdi - bas >= self.pencere_sn:
            bas, sayac = simdi, 0
        return bas, sayac

    def say(self, anahtar: str) -> int:
        """Sayacı bir artırır, yeni değeri döndürür."""
        simdi = self._saat()
        self._temizle(simdi)
        bas, sayac = self._guncel(anahtar, simdi)
        self._kayit[anahtar] = (bas, sayac + 1)
        return sayac + 1

    def sayac(self, anahtar: str) -> int:
        return self._guncel(anahtar, self._saat())[1]

    def kalan_sn(self, anahtar: str) -> int:
        bas, _ = self._guncel(anahtar, self._saat())
        return max(1, int(self.pencere_sn - (self._saat() - bas)) + 1)

    def temizle(self):
        self._kayit.clear()
