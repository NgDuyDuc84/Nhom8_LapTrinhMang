namespace Common
{
    /// <summary>
    /// Cac ma lenh (gia tri cua truong "type") dung chung giua Server va Client.
    /// De la chuoi chu thuong de khi bat goi tin bang Wireshark de doc bang mat.
    /// </summary>
    public static class MessageType
    {
        public const string Register   = "REGISTER";   // Client dang ky voi Server (giai doan 1)
        public const string Ack        = "ACK";        // Xac nhan da nhan duoc thong diep
        public const string Heartbeat  = "HEARTBEAT";  // Tin hieu "toi con song" (giai doan 2)
        public const string Notify     = "NOTIFY";     // Server gui thong bao (giai doan 3)
        public const string Request    = "REQUEST";    // Yeu cau lam gi do
        public const string Response   = "RESPONSE";   // Tra loi cho REQUEST
        public const string Error      = "ERROR";      // Bao loi
        public const string Disconnect = "DISCONNECT"; // Bao ngat ket noi
    }
}
