import json
from datetime import datetime
import httpx
import re
import ast
import asyncio
import sys
from pathlib import Path

# ============================================================
# 第二部分变体：保存为 GitHub 可预览的 Markdown（图文并茂）
# ============================================================

def extract_images_from_content(content):
    """从内容中提取图片 URL"""
    if not content:
        return []
    image_urls = set()
    # Markdown 图片格式 ![alt](url)
    for m in re.finditer(r'!\[.*?\]\((https?://[^\s)]+)\)', content):
        image_urls.add(m.group(1))
    # 常见图片后缀直链
    for m in re.finditer(r'(https?://[^\s]+\.(?:png|jpg|jpeg|gif|webp|svg|bmp))(?:\?[^\s]*)?', content, re.IGNORECASE):
        image_urls.add(m.group(1))
    return list(image_urls)


def _escape_md_table(text):
    """转义 Markdown 表格中的特殊字符"""
    if not text:
        return ''
    return text.replace('|', '\\|').replace('\n', '<br>')


def _parse_date(date_str):
    """解析 ISO 日期字符串"""
    try:
        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        return date_str


def save_conversation_to_md(data):
    """
    将 messageList 数据保存为 GitHub 友好的 Markdown 文件（图文并茂）

    参数:
        data: dict, API 响应数据，需包含 messageList 字段
        output_path: str, 输出文件路径
    """
    message_list = data.get('messageList', [])
    conv_id = (
        message_list[0].get('conversationId', 'unknown')
        if message_list else 'unknown'
    )
    kangbang=(
        ast.literal_eval(message_list[0].get('content'))[0].get('content', 'unknown')
        if message_list else 'unknown'
        )
    kangbang_1=kangbang[:5]

    output_path = f'./{kangbang_1}（{conv_id}）.md'

    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # ---- 统计信息 ----
    model_stats = {}
    user_msg_count = 0
    for msg in message_list:
        role = msg.get('role', '')
        if role == 'USER':
            user_msg_count += 1
        else:
            model_name = msg.get('modelDetail', {}).get('name', role)
            if model_name not in model_stats:
                model_stats[model_name] = {'count': 0, 'credit': 0, 'time': 0}
            model_stats[model_name]['count'] += 1
            model_stats[model_name]['credit'] += msg.get('credit', 0)
            model_stats[model_name]['time'] += msg.get('executionTime', 0)

    lines = []
    lines.append(f'# 📋 对话记录\n')
    lines.append(f'> **对话ID**: `{conv_id}`  ')
    lines.append(f'> **消息总数**: {len(message_list)} · **导出时间**: {now_str}  \n')

    # ---- 统计表格 ----
    lines.append('## 📊 统计信息\n')
    lines.append('| 模型 | 调用次数 | 总积分 | 总耗时(s) |')
    lines.append('| --- | --- | --- | --- |')
    for model, s in model_stats.items():
        lines.append(f'| {model} | {s["count"]} | {s["credit"]} | {s["time"]:.2f} |')
    lines.append(f'| 👤 USER 消息 | {user_msg_count} | - | - |\n')

    # ---- 对话详情（每条消息使用独立区块，支持图文混排）----
    lines.append('## 📝 对话详情\n')

    for idx, msg in enumerate(message_list, 1):
        role = msg.get('role', '')
        content = msg.get('content', '') or ''
        reasoning = msg.get('reasoning', '') or ''
        created_at = _parse_date(msg.get('createdAt', ''))
        exec_time = msg.get('executionTime', 0)
        credit = msg.get('credit', 0)
        model_info = msg.get('modelDetail', {})

        # 角色
        if role == 'USER':
            display_role = '👤 用户'
        else:
            model_name = model_info.get('name', role)
            display_role = f'🤖 {model_name}'

        lines.append(f'### {idx}. {display_role}')
        lines.append(f'> ⏱️ {created_at} · 耗时 {exec_time:.2f}s · 💰 {credit} 积分  \n')

        # ---- 提取图片并展示 ----
        images = extract_images_from_content(content)
        if images:
            lines.append('**📷 图片：**  ')
            for img in images:
                lines.append(f'![图片]({img})  ')
            lines.append('')

        # ---- 文本内容（代码块渲染）----
        # 如果内容看起来像 JSON，用代码块包裹，否则用引用块
        text_content = content.strip()
        if text_content:
            if (text_content.startswith('{') and text_content.endswith('}')) or \
               (text_content.startswith('[') and text_content.endswith(']')):
                try:
                    parsed = json.loads(text_content)
                    lines.append('```json')
                    lines.append(json.dumps(parsed, ensure_ascii=False, indent=2))
                    lines.append('```\n')
                except (json.JSONDecodeError, ValueError):
                    lines.append(f'> {_escape_md_table(text_content)}\n')
            else:
                lines.append(f'> {_escape_md_table(text_content)}\n')

        # ---- 思考过程（折叠块）----
        if reasoning:
            lines.append('<details>')
            lines.append('<summary>💭 思考过程</summary>\n')
            lines.append(f'{reasoning}\n')
            lines.append('</details>\n')

    # ---- 页脚 ----
    lines.append('---\n')
    lines.append(f'*📄 文档结束 · 共 {len(message_list)} 条消息 · 由 Jupyter Notebook 自动生成*  ')

    md_content = '\n'.join(lines)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(md_content)

    print(f'✅ 已保存到 {output_path}')
    print(f'   消息数: {len(message_list)}')
    print(f'   用户消息: {user_msg_count}')
    for model, s in model_stats.items():
        print(f'   {model}: {s["count"]} 次, {s["credit"]} 积分, {s["time"]:.2f}s')


# ============================================================
# 执行：读取 conversation_id.txt，自动下载并保存为 Markdown
# ============================================================

CONV_IDS_FILE = './conversation_id.txt'


def read_conversation_ids(path=CONV_IDS_FILE):
    """从 txt 文件读取 conversation_id。

    规则：
      - 每个 conversation_id 占一行
      - 以 # 开头或空行会被忽略
      - 返回去重后的 id 列表
    """
    conv_ids = []
    try:
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                # 去掉可能的行内注释
                cid = line.split('#')[0].strip()
                if cid and cid not in conv_ids:
                    conv_ids.append(cid)
    except FileNotFoundError:
        print(f'❌ 未找到 {path}，请先创建该文件并填入 conversation_id')
        raise
    return conv_ids


async def fetch_conversation(client, headers, conv_id):
    """获取单个对话记录"""
    cid = "{%22conversationId%22:%22" + conv_id + "%22}"
    url = f"https://api.1min.ai/teams/27f5508a-4eea-4dc3-9f31-3cfc7883f080/features/unified-chat/conversations/messages/after-id?filters={cid}"
    response = await client.get(url, headers=headers)
    return json.loads(response.text)


SKIP_DOWNLOAD = False  # --force 时置 True，强制重新下载已存在的对话


def find_existing_md(conv_id, search_dir='.'):
    """按 conv_id 查找已生成的 md 文件，存在则返回路径，否则 None。"""
    for p in Path(search_dir).glob(f'*（{conv_id}）.md'):
        return p
    return None


async def main():
    global SKIP_DOWNLOAD
    force = '--force' in sys.argv
    conv_ids = read_conversation_ids()
    if not conv_ids:
        print('❌ conversation_id.txt 中没有有效的 conversation_id')
        return

    print(f'📖 共读取到 {len(conv_ids)} 个 conversation_id（文件内已自动去重）')
    if force:
        print('⚙️  --force：忽略已有 md，全部重新下载')

    auth_token = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1dWlkIjoiYjc4YTVhZDEtMTE4Yi00YjZmLWJmZjYtMmU4MjVhYzA1YzMzIiwidG9rZW5WZXJzaW9uIjowLCJpYXQiOjE3OTA5NTk3MjQsImV4cCI6MTc5MTU2NDUyNH0.kN_B4CHJHurNnJ7IgxNtWCM4IlJ2cSEd0gXPSt8HCF0"
    headers = {
        "x-auth-token": f"{auth_token}",
        "Content-Type": "application/json"
    }

    done = skipped = failed = 0
    async with httpx.AsyncClient(verify=False) as client:
        for i, conv_id in enumerate(conv_ids, 1):
            if not force and find_existing_md(conv_id):
                skipped += 1
                continue
            print(f'\n🚀 正在下载 {i}/{len(conv_ids)}: {conv_id}')
            try:
                data = await fetch_conversation(client, headers, conv_id)
                save_conversation_to_md(data)
                done += 1
            except Exception as e:
                failed += 1
                print(f'❌ 下载 {conv_id} 失败: {e}')

    print(f'\n📦 完成：新增 {done} · 跳过（已存在）{skipped} · 失败 {failed}')


if __name__ == "__main__":
    asyncio.run(main())
