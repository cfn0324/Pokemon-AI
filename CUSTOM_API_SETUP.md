# 閰嶇疆鑷畾涔?API 绔偣

鎮ㄧ殑椤圭洰鐜板湪宸查厤缃负浣跨敤鑷畾涔?API 绔偣锛?
## 鉁?宸插畬鎴愮殑閰嶇疆

1. **鍒涘缓 .env 鏂囦欢**锛?   - API Key: `sk-xaz4XmC20cXqqRbO6Kq8q4tXiw0lPk6zBmePWSsdgojNgxB5`
   - API 绔偣: `https://api.ququ233.com/v1`

2. **鏇存柊鎵€鏈?AI 浠ｇ悊**浠ユ敮鎸佽嚜瀹氫箟绔偣锛?   - MainAgent
   - PathfinderAgent
   - PuzzleSolverAgent
   - CriticAgent
   - Summarizer

3. **娣诲姞鑷姩鍔犺浇 .env 鏂囦欢**鐨勫姛鑳?
## 馃殌 蹇€熷紑濮?
### 1. 纭繚瀹夎浜?python-dotenv

```bash
pip install python-dotenv
```

鎴栬€呴噸鏂板畨瑁呮墍鏈変緷璧栵細

```bash
pip install -r requirements.txt
```

### 2. 楠岃瘉閰嶇疆

```bash
python test_setup.py
```

杩欎細妫€鏌ワ細
- 鉁?API 瀵嗛挜鏄惁姝ｇ‘璁剧疆
- 鉁?鑳藉惁杩炴帴鍒拌嚜瀹氫箟 API 绔偣
- 鉁?鎵€鏈変緷璧栨槸鍚﹀畨瑁?
### 3. 鍚姩 AI 浠ｇ悊

```bash
python main.py
```

鎴栦娇鐢ㄥ揩閫熷惎鍔ㄨ剼鏈細

**Windows:**
```cmd
run.bat
```

**Linux/Mac:**
```bash
chmod +x run.sh
./run.sh
```

## 馃摑 閰嶇疆璇︽儏

### .env 鏂囦欢鍐呭

```env
OPENAI_API_KEY=sk-xaz4XmC20cXqqRbO6Kq8q4tXiw0lPk6zBmePWSsdgojNgxB5
OPENAI_BASE_URL=https://api.ququ233.com/v1
```

### 宸ヤ綔鍘熺悊

鎵€鏈?AI 浠ｇ悊鍦ㄥ垵濮嬪寲鏃朵細锛?
1. 妫€鏌ユ槸鍚﹁缃簡 `OPENAI_BASE_URL` 鐜鍙橀噺
2. 濡傛灉璁剧疆浜嗭紝浣跨敤鑷畾涔夌鐐?3. 濡傛灉娌℃湁璁剧疆锛屼娇鐢ㄩ粯璁ょ殑 OpenAI API

浠ｇ爜绀轰緥锛?```python
import os
base_url = os.getenv('OPENAI_BASE_URL')
if base_url:
    self.client = OpenAI(base_url=base_url)
else:
    self.client = OpenAI()
```

## 鈿欙笍 閰嶇疆妯″瀷

濡傛灉鎮ㄧ殑鑷畾涔?API 鏀寔涓嶅悓鐨勬ā鍨嬶紝鍙互鍦?`config.yaml` 涓慨鏀癸細

```yaml
ai:
  model: "GPT-5.1 Codex-sonnet-4-5-20250929"  # 鎴栨偍鐨?API 鏀寔鐨勫叾浠栨ā鍨?  temperature: 0.7
  max_tokens: 4096
```

## 馃攳 娴嬭瘯 API 杩炴帴

杩愯娴嬭瘯鑴氭湰浼氳嚜鍔ㄦ祴璇?API 杩炴帴锛?
```bash
python test_setup.py
```

杈撳嚭绀轰緥锛?```
Testing API connection... OK
  Using custom endpoint: https://api.ququ233.com/v1
```

## 馃搳 鐩戞帶

鍚姩鍚庯紝鏃ュ織浼氭樉绀轰娇鐢ㄧ殑 API 绔偣锛?
```
2024-12-11 11:45:00 - MainAgent - INFO - Using custom API endpoint: https://api.ququ233.com/v1
```

## 馃洜锔?鏁呴殰鎺掗櫎

### 濡傛灉 API 杩炴帴澶辫触

1. **妫€鏌ョ鐐?URL**锛?   ```bash
   echo $OPENAI_BASE_URL
   # 搴旇鏄剧ず: https://api.ququ233.com/v1
   ```

2. **妫€鏌?API 瀵嗛挜**锛?   ```bash
   echo $OPENAI_API_KEY
   # 搴旇鏄剧ず鎮ㄧ殑瀵嗛挜
   ```

3. **娴嬭瘯 API 鐩存帴璁块棶**锛?   ```bash
   curl https://api.ququ233.com/v1/messages \
     -H "x-api-key: sk-xaz4XmC20cXqqRbO6Kq8q4tXiw0lPk6zBmePWSsdgojNgxB5" \
     -H "OpenAI-version: 2023-06-01" \
     -H "content-type: application/json" \
     -d '{
       "model": "GPT-5.1 Codex-sonnet-4-5-20250929",
       "max_tokens": 1024,
       "messages": [{"role": "user", "content": "Hello"}]
     }'
   ```

### 濡傛灉 .env 鏈姞杞?
纭繚 `python-dotenv` 宸插畨瑁咃細

```bash
pip install python-dotenv
```

### 濡傛灉妯″瀷涓嶆敮鎸?
鎮ㄧ殑 API 鍙兘浣跨敤涓嶅悓鐨勬ā鍨嬪悕绉般€傛鏌?API 鏂囨。骞舵洿鏂?`config.yaml`锛?
```yaml
ai:
  model: "your-supported-model-name"
```

## 馃挕 鎻愮ず

1. **淇濇姢 API 瀵嗛挜**锛?   - 涓嶈鎻愪氦 `.env` 鏂囦欢鍒?Git
   - `.gitignore` 宸查厤缃拷鐣?`.env`

2. **澶囦唤閰嶇疆**锛?   - 淇濆瓨 `.env` 鏂囦欢鐨勫壇鏈紙瀹夊叏浣嶇疆锛?   - 璁板綍鎮ㄧ殑 API 绔偣鍜屽瘑閽?
3. **鎴愭湰鐩戞帶**锛?   - 鐩戞帶鎮ㄧ殑 API 浣跨敤鎯呭喌
   - 妫€鏌ヨ嚜瀹氫箟 API 鐨勮璐?
## 鉁?鐜板湪鍙互寮€濮嬩簡锛?
鎵€鏈夐厤缃凡瀹屾垚锛屾偍鍙互锛?
```bash
# 1. 娴嬭瘯璁剧疆
python test_setup.py

# 2. 鍚姩 AI 浠ｇ悊
python main.py
```

AI 灏嗗紑濮嬬帺 Pokemon Red锛屼娇鐢ㄦ偍鐨勮嚜瀹氫箟 API 绔偣锛?
## 馃摎 鐩稿叧鏂囨。

- **蹇€熷紑濮?*: `docs/QUICK_START.md`
- **閰嶇疆璇存槑**: `docs/ADVANCED_USAGE.md`
- **鏁呴殰鎺掗櫎**: `docs/TROUBLESHOOTING.md`
- **鏋舵瀯璇︽儏**: `docs/ARCHITECTURE.md`

绁濇偍鐨?AI 浠ｇ悊鐜╁緱鎰夊揩锛侌煄煠?
