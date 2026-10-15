namespace Common
{
    /// <summary>
    /// Cac hang so dung chung cho ca Server va Client.
    /// </summary>
    public static class Protocol
    {
        // Cong TCP co dinh. Khong ma hoa de Wireshark doc duoc noi dung.
        public const int Port = 5000;

        // Moi thong diep la 1 dong JSON ket thuc bang ky tu xuong dong.
        // Nho ky tu nay ma ben nhan biet duoc ranh gioi giua cac thong diep,
        // vi TCP chi la luong byte va khong giu ranh gioi thong diep.
        public const string LineEnd = "\n";

        // Ten dung o truong "from" cho cac thong diep do Server phat ra.
        public const string ServerName = "SERVER";

        // --- Giai doan 2 ---

        // Cu 5 giay Client gui 1 thong diep HEARTBEAT de bao "toi con song".
        public const int HeartbeatIntervalMs = 5000;

        // Neu qua 15 giay Server khong nhan duoc thong diep nao tu mot may tram
        // thi coi may tram do la Offline.
        public const int OfflineTimeoutMs = 15000;

        // Cu 1 giay Server kiem tra mot lan xem may tram nao da qua han.
        public const int TimeoutCheckIntervalMs = 1000;

        // --- Giai doan 4 ---

        // Ma yeu cau Server gui cho may tram (nam trong truong "payload" cua REQUEST).
        // May tram doc ma nay de biet phai lam gi.
        public const string RequestStationInfo = "STATION_INFO";

        // Server cho may tram tra loi mot yeu cau trong bao lau.
        // Qua thoi gian nay ma chua co tra loi thi coi nhu may tram khong tra loi.
        public const int RequestTimeoutMs = 5000;

        // Cac truong thong tin may tram tra ve duoc viet dang "khoa=gia tri"
        // va ngan cach nhau bang chuoi nay, de khi bat goi tin bang Wireshark
        // van doc duoc noi dung bang mat tren mot dong.
        public const string FieldSeparator = "; ";
    }
}
