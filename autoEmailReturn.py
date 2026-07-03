import poplib
import smtplib
import email
import os
import time
import json
from email.parser import Parser
from email.utils import parsedate_to_datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import decode_header
import logging
from logging.handlers import TimedRotatingFileHandler
import traceback
# 创建日志目录
log_dir = "logs"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

logger = logging.getLogger("daily_logger")
logger.setLevel(logging.INFO)

# 创建一个按天滚动的文件处理器
handler = TimedRotatingFileHandler(
    filename=os.path.join(log_dir, "app.log"),
    when="midnight",
    interval=1,
    backupCount=7,
    encoding="utf-8",
)
handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
# 添加处理器到日志
logger.addHandler(handler)

# 读取配置文件
# 读取配置文件
def load_config():
    with open("config.json", "r", encoding="utf-8") as f:
        return json.load(f)


config = load_config()

# 全局常量和默认值
PROCESSED_UIDS_FILE = "processed_uids.txt"
LAST_CHECK_TIME_FILE = "last_check_time.txt"

EMAIL_ACCOUNT = config.get("EMAIL_ACCOUNT")
EMAIL_PASSWORD = config.get("EMAIL_PASSWORD")
POP3_SERVER = config.get("POP3_SERVER")
SMTP_SERVER = config.get("SMTP_SERVER")
ALLOWED_SENDER = config.get("ALLOWED_SENDER", "")
SLEEP_TIME = int(config.get("SLEEP_TIME", 60))
REPLY_RULES = config.get("REPLY_RULES", {})
DEFAULT_REPLY = config.get("DEFAULT_REPLY", "收到，已安排")
CC_LIST = config.get("CC_LIST", [])
# 计算 2 天前的时间戳
#TWO_DAYS_AGO = time.time() - (2 * 24 * 60 * 60)

# 读取已处理的邮件 UID 集合（UID 是每封邮件的唯一标识，不会因删除邮件而改变）
def read_processed_uids():
    """读取并返回已处理邮件 UID 的集合（持久化在文件中）。"""
    if os.path.exists(PROCESSED_UIDS_FILE):
        with open(PROCESSED_UIDS_FILE, "r", encoding="utf-8") as f:
            return set(line.strip() for line in f if line.strip())
    return set()

# 保存已处理的邮件 UID
def save_processed_uid(uid):
    """将已处理的 UID 追加保存到文件中（容错）。"""
    try:
        with open(PROCESSED_UIDS_FILE, "a", encoding="utf-8") as f:
            f.write(uid + "\n")
    except Exception as e:
        logger.error(f"写入 UID 时发生错误: {e}")
        
# def decode_subject(subject):
#     """解码邮件主题，支持中文"""
#     if subject:
#         decoded_fragments = decode_header(subject)
#         return "".join(
#             (text.decode(charset) if isinstance(text, bytes) else text) 
#             for text, charset in decoded_fragments
#         )
#     return ""
def decode_subject(subject):
    """解码邮件主题，支持多字节编码。"""
    if subject:
        decoded_fragments = decode_header(subject)
        parts = []
        for text, charset in decoded_fragments:
            if isinstance(text, bytes):
                try:
                    parts.append(text.decode(charset or "utf-8", errors="ignore"))
                except Exception:
                    parts.append(text.decode(errors="ignore"))
            else:
                parts.append(text)
        return "".join(parts)
    return ""
def get_last_check_time():
    """获取上次检查邮件的时间戳（用于避免回复历史邮件）。"""
    if os.path.exists(LAST_CHECK_TIME_FILE):
        with open(LAST_CHECK_TIME_FILE, "r", encoding="utf-8") as f:
            try:
                return float(f.read().strip())
            except Exception:
                return time.time() - 1
    return time.time() - 1

def save_last_check_time():
    """保存当前时间戳到文件。"""
    with open(LAST_CHECK_TIME_FILE, "w", encoding="utf-8") as f:
        f.write(str(time.time()))

def get_mail_server():
    """建立并返回 POP3 SSL 连接（发生错误返回 None）。"""
    try:
        server = poplib.POP3_SSL(POP3_SERVER)
        server.user(EMAIL_ACCOUNT)
        server.pass_(EMAIL_PASSWORD)
        return server
    except Exception:
        # 出错时记录日志
        logger.error("连接邮件服务器时发生错误: %s", traceback.format_exc())
        return None

def get_email_content(server, index):
    """使用 POP3 server.retr 获取原始邮件并解析为 email.message.Message 对象。"""
    poplib._MAXLINE = 100000
    resp, lines, octets = server.retr(index)
    raw_bytes = b"\n".join(lines)
    try:
        raw_email = raw_bytes.decode("utf-8")
    except Exception:
        raw_email = raw_bytes.decode("latin1", errors="ignore")
    msg = Parser().parsestr(raw_email)
    return msg

def is_recent_email(msg, last_check_time):
    """判断邮件是否在上次检查时间之后到达（避免回复历史邮件）。"""
    if "Date" not in msg:
        return False
    try:
        email_date = parsedate_to_datetime(msg["Date"])
        return email_date.timestamp() > last_check_time
    except Exception:
        return False

def is_valid_email(msg):
    """判断邮件是否来自允许的发件人（默认仅按发件人过滤，可根据需要扩展规则）。"""
    sender = msg.get("From", "") or ""
    if not ALLOWED_SENDER:
        return True
    return ALLOWED_SENDER in sender
    #return ALLOWED_SENDER in sender and (
    #    any(keyword in subject for keyword in REPLY_RULES.keys())
    #)
    

def get_body(msg):
    """提取邮件正文"""
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                try:
                    body += part.get_payload(decode=True).decode(errors="ignore")
                except Exception:
                    body += str(part.get_payload())
    else:
        try:
            body = msg.get_payload(decode=True).decode(errors="ignore")
        except Exception:
            body = str(msg.get_payload())
    return body.strip()

def create_reply_email(original_email):
    """创建回复邮件（基于主题关键字匹配规则）。"""
    reply = MIMEMultipart()
    reply["From"] = EMAIL_ACCOUNT
    reply["To"] = original_email["From"]
    reply["Subject"] = "Re: " + original_email.get("Subject", "")
    reply["Cc"] = ",".join(CC_LIST)
    reply_content = DEFAULT_REPLY
    subject = decode_subject(original_email.get("Subject", ""))
    for keyword, response in REPLY_RULES.items():
        if keyword in subject:
            reply_content = response
            break
    reply.attach(MIMEText(reply_content, "plain"))
    return reply
def send_reply(reply_email, original_from=None):
    """发送回复邮件。

    `original_from` 是原始发件人地址（可选），发送目标会包含它和抄送列表。
    """
    recipients = []
    if original_from:
        recipients.append(original_from)
    # 加入抄送列表
    recipients.extend(CC_LIST)
    try:
        smtp = smtplib.SMTP_SSL(SMTP_SERVER, 465)
        smtp.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
        smtp.sendmail(reply_email["From"], recipients, reply_email.as_string())
        smtp.quit()
    except Exception:
        logger.error("发送邮件失败: %s", traceback.format_exc())

def main(processed_uids):
    # 获取邮件服务器连接
    server = get_mail_server()
    if server is None:
        # 处理服务器连接失败的情况
        logger.error("无法连接到邮件服务器，跳过邮件列表获取。")
        return
    try:
        resp, messages, octets = server.list()
        # 获取所有邮件的 UID 映射 (消息编号 -> UID)
        uidl_resp, uidl_list, uidl_octets = server.uidl()
        uid_map = {}
        for entry in uidl_list:
            parts = entry.decode('utf-8').split()
            if len(parts) >= 2:
                uid_map[int(parts[0])] = parts[1]

        # 遍历邮件列表
        for msg_data in messages:
            msg_num = int(msg_data.decode('utf-8').split()[0])
            uid = uid_map.get(msg_num)
            if not uid:
                continue
            # 如果已处理过该 UID，则跳过（不受邮件编号重置影响）
            if uid in processed_uids:
                continue
            logger.info(f"收到新邮件，UID: {uid}")
            msg = get_email_content(server, msg_num)
            # 开始处理自动回复
            if is_valid_email(msg):
                logger.info("符合发件人白名单，准备回复")
                reply_email = create_reply_email(msg)
                send_reply(reply_email, original_from=msg.get("From"))
                print(f"已回复邮件: {decode_subject(msg.get('Subject', ''))}")
                logger.info(f"已回复邮件: {decode_subject(msg.get('Subject', ''))}")
            # 保存已处理的 UID（同时更新内存集合和文件）
            processed_uids.add(uid)
            save_processed_uid(uid)
    except Exception as e:
        error_info = traceback.format_exc()
        logger.error("获取邮件列表或处理邮件时发生错误: %s", error_info)
    finally:
        if server:
            try:
                server.quit()
            except Exception as e:
                logger.error("关闭邮件服务器连接时发生错误: %s", e)

def msg_id_init():
    """初始化邮件 UID 追踪：将当前所有邮件的 UID 标记为已处理，避免重复回复旧邮件"""
    processed_uids = read_processed_uids()
    if processed_uids:
        logger.info(f"UID 追踪文件已存在，包含 {len(processed_uids)} 个 UID，跳过初始化")
        return

    server = get_mail_server()
    if server is None:
        logger.error("无法连接到邮件服务器，跳过初始化 UID。")
        return
    try:
        resp, messages, octets = server.list()
        uidl_resp, uidl_list, uidl_octets = server.uidl()
        count = 0
        with open(PROCESSED_UIDS_FILE, "a") as f:
            for entry in uidl_list:
                parts = entry.decode('utf-8').split()
                if len(parts) >= 2:
                    f.write(parts[1] + "\n")
                    count += 1
        logger.info(f"初始化完成，已记录 {count} 封现有邮件的 UID")
    except Exception as e:
        error_info = traceback.format_exc()
        logger.error("初始化 UID 时发生错误: %s", error_info)
    finally:
        if server:
            server.quit()

def main_loop(processed_uids):
    """循环运行邮件检查与自动回复"""
    while True:
        #print("\n开始检查新邮件...")
        logger.info(f"开始检查新邮件...")
        try:
            main(processed_uids)  # 运行自动回复逻辑，使用内存中的 UID 集合
        except Exception as e:
            traceback.print_exc()
            error_info = traceback.format_exc()
            logger.error("An error occurred: %s", error_info)
        
        #print(f"休息 {SLEEP_TIME} 秒后再次收件...")
        time.sleep(int(SLEEP_TIME)) 

if __name__ == '__main__':
    # 先初始化：记录现有所有邮件的 UID
    msg_id_init()
    # 再加载 UID 集合（含初始化写入的），后续由 main_loop 维护在内存中
    processed_uids = read_processed_uids()
    main_loop(processed_uids)
