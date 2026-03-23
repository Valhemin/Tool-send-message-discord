import discord
import json
import random
import asyncio
import os
import aiohttp
import traceback
import re
import google.generativeai as genai

from typing import List, Optional
from rich.console import Console
from rich.theme import Theme
from datetime import datetime, timedelta

custom_theme = Theme({
    "info": "cyan",
    "success": "green",
    "warning": "yellow",
    "error": "bold red",
    "highlight": "magenta"
})
console = Console(theme=custom_theme)

root = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(root, "config.json")
proxies_path = os.path.join(root, "proxies.txt")
proxies_die_path = os.path.join(root, "proxies_die.txt")

count_message_generate = 50
wait_time_min = 30
wait_time_max = 40

class ProxyAPI:
    def __init__(self, console):
        self.console = console
        self.has_proxy = False
        self.proxy_file_exists = False

    async def _test_proxy_async(self, proxy_url: str) -> bool:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://api.myip.com",
                    proxy=proxy_url,
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as response:
                    return response.status == 200
        except Exception:
            return False

    async def load_proxies(self) -> List[str]:
        # Kiểm tra xem file proxy có tồn tại không
        if not os.path.exists(proxies_path):
            with open(proxies_path, "w", encoding="utf-8") as f:
                self.console.print(f"[info]Created empty {proxies_path} file.[/info]")
                self.proxy_file_exists = False
                return []

        # Đọc danh sách proxy từ file
        with open(proxies_path, "r", encoding="utf-8") as f:
            proxy_urls = [line.strip() for line in f if line.strip()]
            
        if not proxy_urls:
            self.proxy_file_exists = False
            return []
        else:
            self.proxy_file_exists = True

        tasks = [self._test_proxy_async(proxy) for proxy in proxy_urls]
        results = await asyncio.gather(*tasks)

        valid_proxies = [
            proxy for proxy, is_valid in zip(proxy_urls, results) if is_valid
        ]
        dead_proxies = [
            proxy for proxy, is_valid in zip(proxy_urls, results) if not is_valid
        ]

        if valid_proxies:
            self.has_proxy = True
        else:
            self.has_proxy = False

        if dead_proxies:
            self.console.print(f"[warning]{len(dead_proxies)} dead proxies saved to {proxies_die_path}[/warning]")
            with open(proxies_die_path, "w", encoding="utf-8") as f:
                f.write("\n".join(dead_proxies))

        return valid_proxies

class GeminiAPI:
    def __init__(self, api_key: str = '', language: str = 'English', console: any = None):
        self.console = console
        self.is_available = False
        self.used_jokes = set()
        self.jokes_cache = []
        self.last_joke = ""
        self.language = language
        
        # Quản lý giới hạn API
        self.requests_count = 0
        self.reset_time = datetime.now() + timedelta(minutes=60)  # Reset counter mỗi giờ
        self.max_requests_per_hour = 120  # Giới hạn mặc định (điều chỉnh theo giới hạn của bạn)
        self.cooldown_active = False
        self.cooldown_until = None
        
        # Chat session
        self.chat_session = None
        self.model = None
        
        if not api_key or api_key == "Your Gemini API Key":
            return
            
        try:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel('gemini-1.5-flash-latest')
            
            # Tạo một chat session dùng chung cho tất cả các tương tác
            self.chat_session = self.model.start_chat(
                history=[
                    {
                        "role": "user",
                        "parts": [f"Tôi sẽ sử dụng bạn để tạo các tin nhắn ngẫu nhiên và trả lời tương tác với những người khác bằng tin nhắn trong một server Discord. Hãy tuân theo các quy tắc sau trong mọi phản hồi của bạn. LƯU Ý: PHẢI trả lời bằng ngôn ngữ {self.language}:"]
                    },
                    {
                        "role": "model", 
                         "parts": ["Tôi đã sẵn sàng hỗ trợ bạn tạo tin nhắn và trả lời cho server Discord. Tôi sẽ tuân theo quy tắc của bạn và sẽ trả lời bằng ngôn ngữ bạn yêu cầu."]
                    },
                    {
                        "role": "user",
                        "parts": ["""
                        Quy tắc tin nhắn khi được yêu cầu 'TẠO TIN NHẮN':
                        1. Tạo tin nhắn ngắn gọn (8-50 từ), độ dài không đồng đều để tạo cảm giác tự nhiên.
                        2. Dùng ngữ điệu tự nhiên, có thể chứa từ đệm như “Ủa”, “Thiệt hông”, “Trời đất ơi”.
                        3. Đa dạng cấu trúc câu: ngắn, dài, hỏi, châm biếm, hài hước, kể chuyện.
                        4. Mỗi tin nhắn phải hoàn toàn khác biệt so với tin nhắn trước đó.
                        5. Nội dung tin nhắn có thể là quan điểm cá nhân, hài hước, nhận xét, câu hỏi mở.
                        6. Tránh dùng câu hỏi chung chung như “Ai online?”, “Mọi người thế nào?”.
                        7. Có thể thêm yếu tố meme, so sánh hài hước, hoặc cảm xúc mạnh.
                        8. Tin nhắn có thể gợi mở để người khác dễ tương tác.
                        9. Không sử dụng giọng điệu trung lập quá nhiều, hãy thể hiện cá tính.
                        10. Nội dung có thể là lời kể, nhận xét, câu hỏi mở, hoặc bình luận vui nhộn.
                        11. Không sử dụng các dấu như !, ?, ;, . ở cuối câu, không sử dụng các kí tự đặc biệt như #, $, [, ] trong câu, trong cả câu hãy viết thường không viết các kí tự hoa trong đó.
                        
                        Quy tắc trả lời khi nhận được 'TRẢ LỜI' và nội dung tin nhắn:
                        1. Trả lời ngắn gọn, giống như đang trò chuyện thực sự, đùa vui lại cũng được.
                        2. Phản hồi phải liên quan đến nội dung được đề cập.
                        3. Thể hiện cá tính, đôi khi hài hước.
                        4. Không giải thích dài dòng, chỉ trả lời như bạn bè chuyện trò.
                        
                        Một số ví dụ, yêu cầu minh hoạ tin nhắn trả về như sau:
                        1. Loại bỏ các câu hỏi rập khuôn như "Có ai online không?"
                        - Thay vì: Tin nhắn mở đầu chung chung như "Ai online không?"
                        - Sử dụng: Bắt đầu bằng một câu chuyện, quan điểm cá nhân hoặc câu hỏi mở thú vị.
                        2. Đa dạng hóa kiểu tin nhắn
                        - Thêm các loại tin nhắn khác nhau, như:
                            - Hài hước: "Ví mình còn đúng 0.0001 BTC, đủ để mua một giấc mơ giàu sang."
                            - Thắc mắc: "Hôm nay có dự án nào ra mắt ngon không nhỉ? 👀"
                            - Tạo tranh luận: "Nếu chỉ được chọn một coin để hold 5 năm, anh em chọn gì?"
                            - Tự sự: "Mỗi lần định cắt lỗ thì nó lại pump lên, vũ trụ đang troll tui à?"
                            - Bâng quơ: "Không ai hỏi nhưng tôi vẫn muốn nói: Crypto đúng là trò chơi của cảm xúc."
                            
                        3. Cho phép sự tự nhiên và ngẫu nhiên
                        - Thêm yếu tố cảm xúc, cách nói chuyện đời thường:
                            - "Trời ơi, nhìn giá BTC mà tim tui muốn rớt ra ngoài! Ai cứu với 😭"
                            - "Hold coin mà cứ như chơi tàu lượn siêu tốc, lúc nào cũng thót tim!"
                            - "Sáng ngủ dậy check giá, mém nữa đập luôn điện thoại... Ai đồng cảm?"
                            
                        4. Thêm các yếu tố ngôn ngữ dân dã, meme, teencode nhẹ
                        - "Thị trường xanh đỏ lẫn lộn, hold mà run tay vl 😵‍💫"
                        - "Tự nhủ không FOMO nữa mà thấy giá pump là nhảy vào liền, ai giống tui? 🥲"
                        - "Giá tụt nhanh hơn crush rep tin nhắn của tui :)))"
                        5. Thêm Ngữ Điệu và Cách Biểu Đạt Gần Gũi
                        - Yêu cầu tin nhắn có thể chứa từ đệm, biểu cảm tự nhiên, kiểu như:
                            - "Ủa, tự nhiên thấy giá xanh xanh, có chuyện gì hot hông anh em?"
                            - "Trời đất ơi, cái ví của tui nó bay màu kìa 🥲"
                            - "Thiệt luôn, sáng dậy thấy giá mà mém xỉu ngang..."
                            - "Mấy ông nghĩ sao, giờ còn kịp vào kèo hông?"
                        6. Biến Đổi Cấu Trúc Câu Nhiều Hơn    
                        - Hiện tại, nếu bot tạo tin nhắn theo một kiểu nhất định, có thể bị nhàm chán.
                        - Yêu cầu cấu trúc câu đa dạng hơn, có thể là:
                        - Một câu ngắn dứt khoát: "Chốt lời xong thấy giá bay tiếp. Đau ghê."
                        - Một câu dài đầy cảm xúc: "Mới bảo không FOMO nữa mà nhìn giá pump xong tay cứ tự động bấm lệnh, ai cứu với!"
                        - Một câu hỏi thẳng vấn đề: "Airdrop con nào xịn mà chưa ai để ý không?"
                        7. Yêu Cầu Có Tương Tác Gián Tiếp
                        - Thay vì chỉ tạo câu nói độc lập, yêu cầu bot tạo câu gợi mở để có thể tiếp tục cuộc trò chuyện.
                            - "Mấy ông nghĩ sao, BTC lên 100K trong năm nay có thật không?"
                            - "Tui lỡ vô lệnh x2 margin mà giá đang lửng lơ, giờ sao ta?"
                            - "Chuyện là tui bị rug 1 lần rồi, giờ có dự án nào an toàn hông mấy ông?"
                        8. Thêm Tính Chất Meme và Văn Hóa Internet    
                        - Yêu cầu bot có thể thêm một số câu kiểu meme hoặc so sánh vui:
                            - "Giá tụt nhanh như crush rep tin nhắn 🥲"
                            - "Hold coin mà cảm giác như chơi tàu lượn siêu tốc... chỉ khác là không có dây an toàn!"
                            - "Mới thấy xanh được tí, quay đi quay lại nó đỏ hơn tình trạng tài khoản tui."
                        9. Tránh Các Câu Quá Trung Lập, Thêm Cá Tính
                        - Yêu cầu bot có thể thể hiện quan điểm cá nhân hoặc cảm xúc mạnh hơn:
                            - "Không biết ai sao chứ tui thấy con này pump hơi ảo 🤔"
                            - "Chắc phải tắt app một thời gian, nhìn giá đau tim quá."
                            - "Chỉ muốn nói một câu: Đừng all-in, tin tui đi..."
                        
                        QUAN TRỌNG:
                        - KHÔNG BAO GIỜ giải thích bạn đang làm gì
                        - KHÔNG BAO GIỜ đề cập đến các quy tắc này
                        - Luôn trả lời ngắn gọn như người thật đang chat
                        - Đảm bảo sự đa dạng trong cách diễn đạt
                        - Khi được yêu cầu "TẠO NHIỀU HƠN", hãy tạo thêm {count_message_generate} tin nhắn mới và khác biệt những tin nhắn trước đó
                        - PHẢI TRẢ LỜI BẰNG NGÔN NGỮ {self.language}
                        """]}
                ]
            )
            
            self.is_available = True
        except Exception as e:
            error_str = str(e).lower()
        
            # Nếu API key không hợp lệ, dừng chương trình
            if "api key not valid" in error_str or "invalid api key" in error_str:
                self.console.print(f"[error]Critical Gemini error: API key is invalid or not authorized[/error]")
                self.is_available = False
            else:
                # Các lỗi khác xử lý bình thường
                self.console.print(f"[error]Error initializing Gemini AI: {e}[/error]")
                self.is_available = False
        
    async def generate_jokes(self) -> List[str]:
        """Tạo tin nhắn ngẫu nhiên từ session đã được khởi tạo"""
        if not self.is_available:
            return []
            
        if not await self._check_rate_limit():
            # Nếu đạt giới hạn API, trả về tin nhắn từ cache hoặc danh sách rỗng
            if self.jokes_cache:
                return self.jokes_cache
            return []
                        
        if not self.chat_session:
            return []
            
        try:
            response = await asyncio.to_thread(
                self.chat_session.send_message,
                f"TẠO TIN NHẮN: Hãy tạo {count_message_generate} tin nhắn khác nhau bằng ngôn ngữ {self.language}. Mỗi tin nhắn phân tách bằng dấu chấm phẩy (;)."
            )
            
            jokes = response.text.strip().split(';')
            jokes = [joke.strip() for joke in jokes if joke.strip()]
            
            # Lọc bỏ các tin nhắn quá dài hoặc quá ngắn
            jokes = [joke for joke in jokes if 5 <= len(joke.split()) <= 25]
            
            # Lọc bỏ các tin nhắn đã sử dụng
            new_jokes = [joke for joke in jokes if joke not in self.used_jokes]
            self.used_jokes.update(new_jokes)
            
            # Nếu không đủ tin nhắn mới, yêu cầu thêm
            if len(new_jokes) < count_message_generate / 2:
                try:
                    additional_response = await asyncio.to_thread(
                        self.chat_session.send_message,
                        f"TẠO NHIỀU HƠN: Tôi cần thêm nhiều tin nhắn khác bằng ngôn ngữ {self.language}, hãy đảm bảo chúng hoàn toàn khác với những tin trước đó."
                    )
                    
                    additional_jokes = additional_response.text.strip().split(';')
                    additional_jokes = [joke.strip() for joke in additional_jokes if joke.strip()]
                    additional_jokes = [joke for joke in additional_jokes if 5 <= len(joke.split()) <= 25]
                    additional_new_jokes = [joke for joke in additional_jokes if joke not in self.used_jokes]
                    self.used_jokes.update(additional_new_jokes)
                    
                    new_jokes.extend(additional_new_jokes)
                except Exception as e:
                    self.console.print(f"[error]Error generating additional jokes: {e}[/error]")
            
            return new_jokes
        except Exception as e:
            self.console.print(f"[error]Error generating jokes: {e}[/error]")
            self._handle_error(e, "message generation")
            return []
    
    async def generate_reply(self, message_content: str) -> str:
        """Tạo phản hồi cho nội dung tin nhắn sử dụng chat session."""
        if not self.is_available:
            return ""  # Trả về chuỗi rỗng thay vì dùng default replies
        
        if not await self._check_rate_limit():
            return ""  # Trả về chuỗi rỗng khi đạt giới hạn
        
        try:
            # Sử dụng session đã có
            response = await asyncio.to_thread(
                self.chat_session.send_message,
                f"TRẢ LỜI: Hãy trả lời tin nhắn sau bằng ngôn ngữ {self.language}: \"{message_content}\""
            )
            
            reply = response.text.strip()
            
            # Loại bỏ các giải thích không cần thiết
            reply_lines = reply.split('\n')
            clean_reply = reply_lines[0] if reply_lines else reply
            
            # Loại bỏ các dấu ngoặc kép nếu có
            clean_reply = clean_reply.strip('"')
            
            return clean_reply
        except Exception as e:
            self.console.print(f"[error]Error generating reply: {e}[/error]")
            self._handle_error(e, "message generation")

    async def get_joke(self) -> str:
        try:
            # Kiểm tra cache và bổ sung nếu cần
            if not self.jokes_cache or len(self.jokes_cache) < 5:  # Duy trì ít nhất 5 tin nhắn trong cache
                # Kiểm tra tình trạng giới hạn API
                if await self._check_rate_limit():
                    try:
                        new_jokes = await self.generate_jokes()
                        if new_jokes:
                            self.jokes_cache.extend(new_jokes)
                    except Exception as e:
                        self.console.print(f"[error]Error refreshing joke cache: {e}[/error]")
            
            # Nếu không có joke trong cache
            if not self.jokes_cache:
                return ""
            else:
                # Chọn một câu khác với câu trước đó nếu có thể
                available_jokes = [j for j in self.jokes_cache if j != self.last_joke]
                if not available_jokes and len(self.jokes_cache) > 0:
                    available_jokes = self.jokes_cache
                    
                joke_index = random.randint(0, len(available_jokes) - 1)
                joke = available_jokes[joke_index]
                self.jokes_cache.remove(joke)
            
            self.last_joke = joke
            return joke
        except Exception as e:
            self._handle_error(e, "message generation")
            return []
    
    def _handle_error(self, e: Exception, context: str = "operation"):
        """Xử lý lỗi từ Gemini API một cách nhất quán"""
        error_str = str(e).lower()
        
        # Kiểm tra API key không hợp lệ - dừng chương trình
        if ("api key not valid" in error_str or 
            "invalid api key" in error_str or 
            "authentication" in error_str or 
            "unauthorized" in error_str):
            self.console.print(f"[error]Critical Gemini error: API key is invalid or not authorized[/error]")
            self.is_available = False
                    
        # Kiểm tra lỗi rate limit - vẫn xử lý cooldown
        elif "quota" in error_str or "limit" in error_str or "rate" in error_str:
            self.console.print("[warning]API rate limit reached. Activating cooldown mode.[/warning]")
            self.cooldown_active = True
            self.cooldown_until = datetime.now() + timedelta(minutes=30)
            return False
        
        # Lỗi không xác định
        self.console.print(f"[error]Error during Gemini {context}: {e}[/error]")
        return False
    
    async def _check_rate_limit(self):
        """Kiểm tra và quản lý giới hạn API"""
        current_time = datetime.now()
        
        # Reset counter nếu đã hết thời gian làm mới
        if current_time > self.reset_time:
            self.requests_count = 0
            self.reset_time = current_time + timedelta(minutes=60)
            self.cooldown_active = False
            self.cooldown_until = None
            return True
            
        # Nếu đang trong thời gian cooldown
        if self.cooldown_active:
            if current_time < self.cooldown_until:
                remaining = (self.cooldown_until - current_time).total_seconds() / 60.0
                self.console.print(f"[warning]API rate limit cooldown active. Resuming in {remaining:.1f} minutes[/warning]")
                return False
            else:
                # Hết thời gian cooldown
                self.cooldown_active = False
                self.requests_count = 0
                return True
                
        # Kiểm tra nếu đạt giới hạn
        if self.requests_count >= self.max_requests_per_hour:
            self.cooldown_active = True
            self.cooldown_until = current_time + timedelta(minutes=10)  # Cooldown 10 phút
            self.console.print(f"[warning]API rate limit reached. Activating cooldown for 10 minutes[/warning]")
            return False
            
        # Tăng bộ đếm và cho phép request
        self.requests_count += 1
        return True

    def check_api_status(self) -> dict:
        """Trả về thông tin về tình trạng sử dụng API"""
        return {
            "is_available": self.is_available,
            "requests_made": self.requests_count,
            "max_requests": self.max_requests_per_hour,
            "reset_time": self.reset_time.strftime("%H:%M:%S"),
            "cooldown_active": self.cooldown_active,
            "cooldown_until": self.cooldown_until.strftime("%H:%M:%S") if self.cooldown_until else None,
            "cache_size": len(self.jokes_cache)
        }
        
class MessageHandler:
    def __init__(self, client: discord.Client, server_configs: List[dict], message_count: int, time_delay: int):
        self.client = client
        self.server_configs = server_configs
        self.max_message_count = message_count
        self.time_delay = time_delay
        self.message_count = 0
        self.last_break_time = None
        self.is_on_break = False
        self.server_last_message_time = {}
        self.username = None
        self.sent_messages = set()
     
    async def set_username(self, username=None):
        """Lưu lại tên người dùng để hiển thị trong log"""
        if username:
            self.username = username
        elif self.client.user:
            self.username = f"{self.client.user.name}" if not hasattr(self.client.user, "discriminator") else f"{self.client.user.name}#{self.client.user.discriminator}"
        else:
            self.username = "Unknown"    

    async def wait_between_server_messages(self, server_id):
        """Đợi giữa các tin nhắn đến cùng một server"""
        current_time = datetime.now()
        if server_id in self.server_last_message_time:
            time_since_last = (current_time - self.server_last_message_time[server_id]).total_seconds()
            # If less than minimum time between server messages, wait
            if time_since_last < 20:  # Minimum 20 seconds between messages to the same server
                delay = random.uniform(20, 40) - time_since_last
                if delay > 0:
                    await asyncio.sleep(delay)

    async def update_message_count(self):
        """Cập nhật số tin nhắn đã gửi và kiểm tra nếu cần phải break"""
        self.message_count += 1
        if self.message_count >= self.max_message_count:
            self.is_on_break = True
            self.last_break_time = datetime.now()
            self.message_count = 0
            console.print(f"[highlight]{self.username} - Taking a break for {self.time_delay} minutes...[/highlight]")

    async def send_message(self, message: str):
        if self.is_on_break:
            return
        
        for config in self.server_configs:
            try:
                server_id = config.get("server_id")
                channel_id = config.get("channel_id")
                mention_id = config.get("mention_id")
                
                if not channel_id:
                    continue
                
                # Đợi giữa các tin nhắn đến cùng một server
                await self.wait_between_server_messages(server_id)
                
                channel = await self.client.fetch_channel(int(channel_id))
                if not channel:
                    continue

                # Xử lý mention nếu có
                mention = ""
                if mention_id or mention_id != 0:
                    try:
                        member = await channel.guild.fetch_member(mention_id)
                        if member:
                            mention = f"<@{member.id}> "
                    except:
                        pass

                await channel.send(f"{mention}{message}")
                console.print(f"[success]{self.username} - Sent message to server {channel.guild.name}, channel: {channel.name} with content: {message}[/success]")
                
                # Mark message as sent only after successfully sending
                if message not in self.sent_messages:
                    self.sent_messages.add(message)
                
                # Update the last message time for this server
                self.server_last_message_time[server_id] = datetime.now()

                # Add random delay between server messages (20-40 seconds)
                if len(self.server_configs) > 1:
                    server_delay = random.uniform(20, 40)
                    await asyncio.sleep(server_delay)
                    
                # Cập nhật số tin nhắn đã gửi và kiểm tra break
                await self.update_message_count()
                
            except Exception as e:
                console.print(f"[error]{self.username} - Error sending message: {e}[/error]")
                
    async def fetch_random_message(self, channel_id: int) -> Optional[discord.Message]:
        """Fetch a random message from the channel history."""
        try:
            if not self.username:
                await self.set_username()
            
            channel = await self.client.fetch_channel(channel_id)
            if not channel:
                return None
            
            # Get last 50 messages
            messages = []
            async for msg in channel.history(limit=50):
                # Don't reply to bot's own messages or system messages
                if (msg.author.id != self.client.user.id 
                    and not msg.author.bot 
                    and msg.content 
                    and len(msg.content) >= 5):
                    messages.append(msg)
            
            if not messages:
                return None
                
            # Return a random message
            return random.choice(messages)
        except Exception as e:
            console.print(f"[error]{self.username} - Error fetching random message: {e}[/error]")
            return None
    
    async def reply_to_message(self, message: discord.Message, reply_content: str):
        """Reply to a specific message in Discord."""
        if self.is_on_break:
            return
            
        try:            
            await message.reply(reply_content, mention_author=False)
            console.print(f"[success]{self.username} - Replied to {message.author}'s message with: {reply_content}[/success]")
            
            # Cập nhật số tin nhắn đã gửi và kiểm tra break
            await self.update_message_count()
            
        except Exception as e:
            console.print(f"[error]{self.username} - Error replying to message: {e}[/error]")
            
    async def check_break_status(self):
        """Kiểm tra nếu đã hết thời gian break"""
        if self.is_on_break and self.last_break_time:
            if datetime.now() - self.last_break_time >= timedelta(minutes=self.time_delay):
                self.is_on_break = False
                console.print(f"[info]{self.username} - Break time over, resuming message sending...[/info]")

class DiscordBot(discord.Client):
    def __init__(self, token: str, proxy: str, server_configs: List[dict], messages: List[str] = None, message_count: int = 10, time_delay: int = 5):
        if proxy:
            connector = aiohttp.TCPConnector(ssl=False)
            self.client = discord.Client(
                connector=connector,
                proxy=proxy
            )
        else:
            self.client = discord.Client()
            
        self.token = token
        self.server_configs = server_configs
        self.message_handler = MessageHandler(self.client, server_configs, message_count, time_delay)
        self.gemini_handler = None
        self.running = True
        self.use_gemini = False
        self.username = None
        self.messages = messages or []

    async def start(self, gemini_handler: GeminiAPI):
        self.gemini_handler = gemini_handler
        self.use_gemini = gemini_handler.is_available
        
        @self.client.event
        async def on_ready():
            if self.client.user:
                self.username = f"{self.client.user.name}" if not hasattr(self.client.user, "discriminator") else f"{self.client.user.name}#{self.client.user.discriminator}"
                await self.message_handler.set_username(self.username)
    
            console.print(f"\n[success]Logged in as {self.client.user}[/success]")
            console.print(f'[info]{self.username} - Starting to send messages...[/info]')
            asyncio.create_task(self.message_loop())

        try:
            await self.client.start(self.token)
        except Exception as e:
            console.print(f"[error]{self.username} - Error starting bot: {e}[/error]", traceback.format_exc())

    async def choose_action(self) -> str:
        # Kiểm tra Gemini trước tiên
        if self.gemini_handler and not self.gemini_handler.is_available:
            self.use_gemini = False
            # Chỉ chọn predefined nếu có tin nhắn
            if self.messages:
                return "predefined"
            return "default"
        
        # Reset các action có thể
        possible_actions = []
        
        # Phân bổ trọng số cho các action
        # if self.use_gemini:
        #     possible_actions.extend(["reply"] * 5)  # Reply: 50% 
        
        # if self.messages:
        #     possible_actions.extend(["predefined"] * 3)  # Predefined: 30%
        
        # if self.use_gemini:
        #     possible_actions.extend(["gemini"] * 2)  # Gemini: 20%
        
        # Nếu không có action nào khả dụng
        if not possible_actions:
            if self.messages:
                return "predefined"
            return "default"
        
        # Chọn action
        action = random.choice(possible_actions)
        return action
    
    async def handle_reply_action(self) -> bool:
        """Xử lý hành động reply và trả về True nếu thành công"""
        found_message = False
        # Xáo trộn configs để thử các kênh khác nhau
        shuffled_configs = list(self.server_configs)
        random.shuffle(shuffled_configs)
        
        for config in shuffled_configs:
            random_message = await self.message_handler.fetch_random_message(int(config["channel_id"]))
            if random_message:
                # Tạo phản hồi sử dụng Gemini
                reply_content = await self.gemini_handler.generate_reply(random_message.content)
                
                # Kiểm tra nếu phản hồi rỗng, bỏ qua và tiếp tục vòng lặp
                if not reply_content:
                    continue
                
                reply_content = self.clean_punctuation(reply_content)
                await self.message_handler.reply_to_message(random_message, reply_content)
                found_message = True
                break
        
        return found_message
    
    async def message_loop(self):
        while self.running:            
            if self.gemini_handler and self.gemini_handler.cooldown_active:
                # Nếu API đang trong cooldown
                self.use_gemini = False
                console.print(f"[warning]{self.username} - Gemini API in cooldown. Switching to predefined messages only.[/warning]")
            elif self.gemini_handler and not self.gemini_handler.cooldown_active and not self.use_gemini and self.gemini_handler.is_available:
                # Khôi phục sử dụng Gemini khi hết cooldown
                self.use_gemini = True
                console.print(f"[info]{self.username} - Gemini API available again. Resuming normal operation.[/info]")
            
            await self.message_handler.check_break_status()
            
            if not self.message_handler.is_on_break:
                if random.random() < 0.2:  # 20% cơ hội chỉ đọc tin nhắn
                    console.print(f"[info]{self.username} - Just read messages, don't send anything...[/info]")
                    await asyncio.sleep(random.uniform(5, 20))
                    continue
                # Mỗi lần lặp, ngẫu nhiên chọn giữa ba hành động
                action = await self.choose_action()
                console.print(f"[info]{self.username} - Selected action: {action}[/info]")
                
                if action == "reply" and self.use_gemini and self.gemini_handler.is_available:
                    found_message = await self.handle_reply_action()
                    if not found_message:
                        # Nếu không tìm thấy tin nhắn để trả lời, chỉ cần bỏ qua
                        # Chờ một chút trước khi thử vòng lặp tiếp theo
                        await asyncio.sleep(random.uniform(5, 10))
                        continue
                
                elif action == "predefined" and self.messages:
                    # Chọn một tin nhắn khác với tin nhắn cuối cùng đã gửi
                    message = await self.get_predefined_message()
                    if message:
                        await self.message_handler.send_message(message)
                    else:
                        console.print(f"[warning]{self.username} - Failed to get predefined message. Skipping this turn.[/warning]")
                        await asyncio.sleep(random.uniform(5, 10))
                        continue
                    
                else:  # action == "gemini"
                    # Sử dụng Gemini để tạo tin nhắn mới
                    if self.use_gemini and self.gemini_handler.is_available:
                        joke = await self.gemini_handler.get_joke()
                        
                        # Kiểm tra nếu không nhận được phản hồi từ Gemini
                        if not joke:
                            console.print(f"[warning]{self.username} - Failed to get message from Gemini. Skipping this turn.[/warning]")
                            # Chờ một chút trước khi thử vòng lặp tiếp theo
                            await asyncio.sleep(random.uniform(5, 10))
                            continue  # Bỏ qua lượt này
                            
                        await self.message_handler.send_message(joke)
                    elif self.messages:
                        # Fallback to predefined if Gemini unavailable but we have messages
                        message = await self.get_predefined_message()
                        await self.message_handler.send_message(message)
                    else:
                        # Nếu không có Gemini và không có tin nhắn, bỏ qua vòng lặp hiện tại
                        console.print(f"[warning]{self.username} - No message source available. Skipping this turn.[/warning]")
                        await asyncio.sleep(random.uniform(5, 10))
                        continue
                
                # Random delay between messages (5-10 seconds in your code)
                delay = random.uniform(wait_time_min, wait_time_max)
                console.print(f"[info]{self.username} - Waiting {delay:.1f} seconds before next message...[/info]")
                await asyncio.sleep(delay)
            else:
                await asyncio.sleep(60)
    
    async def transform_message(self, messages: list) -> list:
        """Sử dụng Gemini để biến đổi tin nhắn, thay đổi vài từ để tạo phiên bản mới"""
        if not self.use_gemini or not self.gemini_handler and not self.gemini_handler.is_available:
            return ''
            
        try:
            message_list = ";".join([f"Tin nhắn {i+1}: {msg}" for i, msg in enumerate(messages)])
        
            transformation_prompt = f"""Dưới đây là danh sách các tin nhắn:
            {message_list}
            Hãy viết lại MỖI tin nhắn bằng cách thay đổi 4, 20 từ hoặc cách diễn đạt, nhưng giữ nguyên ý nghĩa và độ dài tương tự hoặc dài hơn 30%.
            Giữ định dạng emoji nếu có.
            Trả về danh sách tin nhắn mới theo định dạng:
            [tin nhắn mới 1];[tin nhắn mới 2];[tin nhắn mới 3];
            ...và tiếp tục
            """
            
            response = await self.gemini_handler.generate_reply(transformation_prompt)
            if not response:
                return []
            
            # Xử lý phản hồi từ Gemini
            transformed_messages = []
            message_parts = response.strip().split(';')
            
            # Làm sạch và lọc các tin nhắn từ phản hồi
            for part in message_parts:
                clean_message = part.strip()
                # Loại bỏ các định dạng số đầu dòng nếu có
                if clean_message:
                    # Loại bỏ định dạng số như "1. " hoặc "[1] " nếu có
                    clean_message = re.sub(r'^\d+[\.\)\]]\s*', '', clean_message)
                    # Loại bỏ "Tin nhắn X: " nếu có
                    clean_message = re.sub(r'^Tin nhắn \d+:\s*', '', clean_message)
                    clean_message = self.clean_punctuation(clean_message)
                    # Chỉ thêm vào nếu tin nhắn không trống
                    if len(clean_message) > 3:
                        transformed_messages.append(clean_message)
            
            # Đảm bảo có ít nhất một số lượng tin nhắn tối thiểu
            if len(transformed_messages) < min(3, len(messages)):
                console.print(f"[warning]{self.username} - Not enough transformed messages generated. Trying again...[/warning]")
                return []
                
            return transformed_messages
                
        except Exception as e:
            console.print(f"[error]{self.username} - Error transforming message: {e}[/error]")
            
    async def get_predefined_message(self) -> str:
        """Lấy tin nhắn từ danh sách được cấu hình, tránh lặp lại gần đây"""
        if not self.messages:
            return ""
        
        # Lọc ra các tin nhắn chưa xuất hiện trong self.message_handler.sent_messages
        available_messages = [m for m in self.messages if m not in self.message_handler.sent_messages]
        
        # Nếu đã dùng hết tất cả tin nhắn trong danh sách
        if not available_messages:
            console.print(f"[info]{self.username} - All messages used. Generating new variations with AI.[/info]")
            
            # Nếu có Gemini và có thể sử dụng, biến đổi tất cả tin nhắn
            if self.use_gemini and self.gemini_handler and self.gemini_handler.is_available:
                # Xử lý tin nhắn theo lô để tránh vượt quá giới hạn của API
                batch_size = 60  # Xử lý tối đa 20 tin nhắn mỗi lô
                new_messages = []
                
                # Chia nhỏ tin nhắn thành các lô để xử lý
                for i in range(0, len(self.messages), batch_size):
                    batch = self.messages[i:i+batch_size]
                    # Gọi hàm transform_message với lô tin nhắn
                    transformed_batch = await self.transform_message(batch)
                    if transformed_batch:
                        new_messages.extend(transformed_batch)
                    else:
                        # Nếu biến đổi thất bại, giữ nguyên tin nhắn gốc cho lô này
                        console.print(f"[warning]{self.username} - Failed to transform batch. Keeping original messages.[/warning]") 
                        new_messages.extend(batch)
                        
                    # Đợi một chút giữa các lô để không vượt quá rate limit
                    await asyncio.sleep(5)
                
                # Nếu tạo được tin nhắn mới
                if new_messages:
                    console.print(f"[success]{self.username} - Successfully transformed messages: {len(new_messages)} new messages created.[/success]")
                    self.messages = new_messages
                    # Reset danh sách đã gửi để sử dụng tin mới
                    self.message_handler.sent_messages = set()
                    # Chọn một tin nhắn mới
                    message = random.choice(self.messages)
                    self.message_handler.sent_messages.add(message)
                    return message
                else:
                    # Nếu hoàn toàn không tạo được tin nhắn mới
                    console.print(f"[warning]{self.username} - Couldn't generate any new messages. Reusing original ones.[/warning]")
                    self.message_handler.sent_messages = set()
                    message = random.choice(self.messages)
                    self.message_handler.sent_messages.add(message)
                    message = self.clean_punctuation(message)
                    return message
            else:
                # Không có Gemini, reset danh sách và chọn tin nhắn ngẫu nhiên
                console.print(f"[info]{self.username} - No Gemini available. Reusing original messages.[/info]")
                self.message_handler.sent_messages = set()
                message = random.choice(self.messages)
                self.message_handler.sent_messages.add(message)
                message = self.clean_punctuation(message)
                return message
        
        # Chọn tin nhắn chưa được dùng gần đây
        message = random.choice(available_messages)
        # Cập nhật tin nhắn đã sử dụng trong MessageHandler
        self.message_handler.sent_messages.add(message)
        message = self.clean_punctuation(message)
        return message
    
    def clean_punctuation(self, text: str) -> str:
        """Loại bỏ các dấu câu không cần thiết, chỉ giữ lại dấu chấm và phẩy."""
        if not text:
            return ""
        
        # Chuyển text về chữ thường
        
        # Giữ lại dấu chấm và phẩy, loại bỏ các dấu câu khác  
        cleaned_text = re.sub(r'[]{}&*%!?;:"\']', '', text)
        
        # Loại bỏ nhiều dấu chấm liên tiếp (như "...")
        cleaned_text = re.sub(r'\.{2,}', '.', cleaned_text)
        
        # Loại bỏ khoảng trắng thừa
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
        text = text.lower()
        
        return cleaned_text
    

async def main():
    if not os.path.exists(config_path):
        console.print(f"[warning]Configuration file not found: {config_path}[/warning]")
        sample_config = {
            "gemini_api_key": "Your Gemini API Key",
            "servers": [
                {
                    "server_id": 12345678,
                    "channel_id": 12345678,
                    "mention_id": 0
                }
            ],
            "tokens": ["your_token_1", "your_token_2"],
            "message_count": 10,
            "time_delay": 5,
            "language": "English",
            "list_message": [
                "Hello!", 
                "Hi there!"
            ]
        }
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(sample_config, f, indent=2)
        console.print(f"[info]Created sample config file at {config_path}. Please edit it with your values.[/info]")
        return
    
    with open("config.json", "r", encoding="utf-8") as f:
        config = json.load(f)
        
    # Khởi tạo proxy control và tải proxies
    proxy_control = ProxyAPI(console=console)
    proxies = await proxy_control.load_proxies()   
    
    # Tải tokens và messages
    server_configs = config.get("servers", [])
    tokens = config.get("tokens", [])
    message_count = int(config.get("message_count", 10))
    time_delay = int(config.get("time_delay", 5))
    messages = config.get("list_message", [])
    
    # Xác thực cấu hình
    if not tokens:
        console.print("[error]Error: No tokens found in configuration.[/error]")
        return
    
    if len(config.get("servers", [])) == 0:
        console.print("[error]Error: No server configurations found in configuration.[/error]")
        return
    
    # Xử lý phân phối tin nhắn
    if len(messages) == 1:
        console.print("[info]Only one message found. Using it for all tokens.[/info]")
        messages = [messages[0] for _ in range(len(tokens))]
    else:
        # Hỏi người dùng có muốn gửi tin nhắn ngẫu nhiên hay theo thứ tự
        choice = 'y' or input("Send messages randomly? (y/n) [Y]: ").lower().strip()
        send_randomly = choice != 'n'  # Mặc định là True trừ khi người dùng nhập 'n'
        print()  # Thêm dòng trống để dễ đọc

        # Chuẩn bị tin nhắn dựa trên lựa chọn của người dùng
        if send_randomly:
            console.print("[info]Sending messages in random order.[/info]")
            # Tạo danh sách tin nhắn có cùng độ dài với tokens
            if len(messages) < len(tokens):
                # Nếu không đủ tin nhắn, lặp lại chúng
                messages = (messages * ((len(tokens) // len(messages)) + 1))[:len(tokens)]
            random.shuffle(messages)
        else:
            console.print("[info]Sending messages sequentially.[/info]")
            # Nếu không đủ tin nhắn, lặp lại chúng
            if len(messages) < len(tokens):
                messages = (messages * ((len(tokens) // len(messages)) + 1))[:len(tokens)]
                
    # Xử lý yêu cầu proxy
    if proxy_control.proxy_file_exists:
        if not proxy_control.has_proxy:
            console.print("\n[error]All proxies are dead. Stopping program.[/error]")
            return
        
        if len(proxies) < len(tokens):
            console.print(f"\n[warning]Warning: Not enough valid proxies ({len(proxies)}) for all tokens ({len(tokens)}).[/warning]")
            console.print(f"[warning]Using only the first {len(proxies)} tokens.[/warning]")
            tokens = tokens[:len(proxies)]
            messages = messages[:len(proxies)]
    else:
        console.print("[info]Running without using proxies.[/info]")
        proxies = []

    gemini_api_key = config.get("gemini_api_key")
    language = config.get("language", "English")
    
    if not gemini_api_key or gemini_api_key == "Your Gemini API Key":
        console.print("\n[warning]No valid Gemini API key found.[/warning]")
        console.print("[info]Running in messages-only mode. Will use only predefined messages.[/info]")
        gemini_handler = GeminiAPI(language=language, console=console)  # Initialize without API key
    else:
        gemini_handler = GeminiAPI(api_key=gemini_api_key, language=language, console=console)
   
    # Create a single list of messages that all bots will share
    # Only create separate message groups if the config explicitly contains grouped messages 
    shared_messages = messages
    
    # Check if the message list contains sublists (grouped messages)
    has_message_groups = any(isinstance(item, list) for item in messages)
    
    # This will hold our bot-specific message lists
    bot_messages = []
    
    if has_message_groups:
        # Handle the case where messages are already organized in groups
        for i in range(len(tokens)):
            if i < len(messages) and isinstance(messages[i], list):
                bot_messages.append(messages[i])
            elif i < len(messages) and not isinstance(messages[i], list):
                bot_messages.append([messages[i]])
            else:
                # If we don't have enough message groups, share the whole list
                bot_messages.append(shared_messages)
    else:
        # All bots will use the same message list
        for _ in range(len(tokens)):
            bot_messages.append(shared_messages)
            
    bots = []
    
    for i, token in enumerate(tokens):
        proxy = proxies[i] if proxies and i < len(proxies) else None
        bot = DiscordBot(
            token=token, 
            messages=bot_messages[i], 
            proxy=proxy, 
            server_configs=server_configs,
            message_count=message_count,
            time_delay=time_delay
        )
        bots.append(bot)

    console.print(f"[highlight]Starting {len(tokens)} clients...[/highlight]\n")
    await asyncio.gather(*(bot.start(gemini_handler) for bot in bots))

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[warning]Script stopped by user[/warning]")
        try:
            # Give gRPC some time to clean up
            loop = asyncio.get_event_loop()
            if loop.is_running():
                pending = asyncio.all_tasks(loop=loop)
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        except Exception:
            pass
    except Exception as e:
        console.print(f"[error]Script error: {str(e)}[/error]")