"""API yanıt modelleri. /docs sayfasındaki örnekler ve alan açıklamaları buradan gelir."""
from pydantic import BaseModel, Field


class Vehicle(BaseModel):
    """Durağa yaklaşan canlı bir araç."""
    hat_no: str | None = Field(None, examples=["114-1"])
    hat_ad: str | None = Field(None, examples=["GÖLBAŞI-KAMPÜS-YURTLAR-AŞTİ-AKKÖPRÜ"])
    arac_no: str = Field(examples=["12-133"])
    dakika: int | None = Field(None, description="Durağa kalan süre (dk). 'Geliyor' ise 0, anlaşılamadıysa null.", examples=[9])
    geliyor: bool = Field(False, description="EGO 'Geliyor' diyorsa true.")
    sure_ham: str = Field("", description="EGO'nun verdiği ham süre metni.", examples=["9 dk"])
    detay: str = Field("", examples=["Körüklü, Engelli"])


class TarifeRow(BaseModel):
    """Canlı aracı olmayan hat için tarife bilgisi (hattın İLK durağından kalkış)."""
    hat_no: str | None = None
    hat_ad: str | None = None
    aciklama: str = Field(examples=["Sonraki Hareket Saati İlk Duraktan 11:00 / 27 dk Sonra"])
    saat: str | None = Field(None, examples=["11:00"])


class ArrivalsOut(BaseModel):
    durak: str = Field(examples=["12579"])
    canli: list[Vehicle]
    tarife: list[TarifeRow]
    bos: bool = Field(False, description="EGO boş liste döndürdü: durakta araç yok ya da numara geçersiz.")
    alindi: str | None = Field(None, description="EGO'dan alındığı zaman.")
    stale: bool = Field(False, description="EGO yanıt vermedi, son geçerli veri gösteriliyor.")


class ProfileOut(BaseModel):
    ad: str = Field(examples=["Test Öğrenci"])
    rol: str = Field(examples=["ogrenci"])
    fakulte: str | None = Field(None, examples=["Mühendislik"])
    kampus: str | None = Field(None, examples=["Gölbaşı 50. Yıl"])
    bildirim_acik: bool = True


class StopOut(BaseModel):
    """Kullanıcının favori durağı ve kampüs hatlarına göre filtrelenmiş canlı araçlar."""
    id: int
    durak_no: str
    ad: str
    bildirim_dk: int = Field(description="Otobüs durağa en fazla kaç dk kala bildirim gelsin.", examples=[10])
    canli: list[Vehicle]
    filtre_aktif: bool = Field(description="false ise kampüsünüz için hat listesi tanımsızdır ve tüm araçlar gösterilir.")
    veri_alinamadi: bool = Field(False, description="Bu durak için EGO verisi alınamadı.")
    stale: bool = False


class NotificationOut(BaseModel):
    id: int
    durak_no: str
    mesaj: str = Field(examples=["Saat 09:00 dersin için Ev durağına yaklaşan otobüsler: 114-1 (5 dk), 115-1 (10 dk)."])
    dakika: int | None = None
    araclar: list[dict] = Field(default_factory=list)
    created_at: str
    sent_at: str | None = Field(None, description="Push gönderildiyse zamanı, yalnızca kaydedildiyse null.")


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class HealthOut(BaseModel):
    durum: str = "ok"
    surum: str
    ozellikler: dict[str, bool] = Field(description="Hangi bileşenlerin açık olduğu (anahtarlar gösterilmez).")


class SearchHit(BaseModel):
    icerik: str
    baslik: str
    madde: str | None = None
    kaynak_url: str | None = None
    score: float


class SearchOut(BaseModel):
    sonuclar: list[SearchHit]


class ScheduleItemOut(BaseModel):
    """Kullanıcının ders programındaki bir satır."""
    id: int
    gun: int = Field(description="Haftanın günü: 1=Pazartesi … 7=Pazar (isoweekday).", examples=[1])
    baslangic: str = Field(description="Başlangıç saati (Europe/Istanbul).", examples=["09:00:00"])
    bitis: str = Field(description="Bitiş saati (Europe/Istanbul).", examples=["10:50:00"])
    baslik: str = Field(examples=["Algoritma ve Programlama"])
    yer: str | None = Field(None, examples=["B-204"])