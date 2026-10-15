using System.Text.Json;
using System.Text.Json.Serialization;

namespace Common
{
    /// <summary>
    /// Mot thong diep cua giao thuc tang ung dung.
    /// Moi thong diep duoc truyen di duoi dang MOT DONG JSON ket thuc bang ky tu '\n'
    /// (xem Protocol.LineEnd) de ben nhan biet duoc ranh gioi giua cac thong diep.
    ///
    /// Vi du mot dong tren duong truyen:
    /// {"type":"REGISTER","id":"a1b2...","from":"PC01","payload":"192.168.1.10","timestamp":"2026-10-12 09:30:00"}
    /// </summary>
    public class LanMessage
    {
        // Cac truong cua giao thuc, ten trong JSON viet chu thuong cho de doc.
        [JsonPropertyName("type")]
        public string Type { get; set; } = "";

        [JsonPropertyName("id")]
        public string Id { get; set; } = "";

        [JsonPropertyName("from")]
        public string From { get; set; } = "";

        [JsonPropertyName("payload")]
        public string Payload { get; set; } = "";

        [JsonPropertyName("timestamp")]
        public string Timestamp { get; set; } = "";

        // Cau hinh dung chung khi doc/ghi JSON.
        private static readonly JsonSerializerOptions JsonOptions = new JsonSerializerOptions
        {
            PropertyNameCaseInsensitive = true,
            WriteIndented = false
        };

        /// <summary>
        /// Tao mot thong diep moi, tu dong sinh "id" va "timestamp".
        /// </summary>
        public static LanMessage Create(string type, string from, string payload)
        {
            LanMessage msg = new LanMessage();
            msg.Type = type;
            msg.From = from;
            msg.Payload = payload ?? "";
            msg.Id = Guid.NewGuid().ToString("N");              // id ngan gon cho de doc
            msg.Timestamp = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss");
            return msg;
        }

        /// <summary>
        /// Chuyen thong diep thanh chuoi JSON (KHONG co ky tu xuong dong o cuoi).
        /// JSON khong cho phep ky tu xuong dong nam trong chuoi nen nguoi nhan luon tach duoc dong dung.
        /// </summary>
        public string ToJson()
        {
            return JsonSerializer.Serialize(this, JsonOptions);
        }

        /// <summary>
        /// Doc mot dong JSON thanh thong diep.
        /// Nem JsonException neu chuoi khong phai JSON hop le.
        /// </summary>
        public static LanMessage FromJson(string jsonLine)
        {
            LanMessage msg = JsonSerializer.Deserialize<LanMessage>(jsonLine, JsonOptions);
            if (msg == null)
            {
                throw new JsonException("Noi dung thong diep rong.");
            }
            return msg;
        }

        /// <summary>Chuoi ngan gon de ghi log.</summary>
        public override string ToString()
        {
            return Type + " | id=" + Id + " | from=" + From + " | payload=" + Payload;
        }
    }
}
