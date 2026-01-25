# 馃帀 椤圭洰宸查厤缃畬鎴愶紒

鎮ㄧ殑 Pokemon AI Agent 鐜板湪宸查厤缃负浣跨敤鎮ㄧ殑鑷畾涔?API 绔偣銆?
## 鉁?閰嶇疆鎽樿

- **API 绔偣**: `https://api.ququ233.com/v1`
- **API 瀵嗛挜**: 宸茶缃紙瀛樺偍鍦?`.env` 鏂囦欢涓級
- **鑷姩鍔犺浇**: 宸查厤缃?`python-dotenv` 鑷姩鍔犺浇鐜鍙橀噺

## 馃殌 绔嬪嵆寮€濮?
### 姝ラ 1: 瀹夎渚濊禆

```bash
pip install -r requirements.txt
```

杩欎細瀹夎鎵€鏈夊繀闇€鐨勫寘锛屽寘鎷細
- `OpenAI` - GPT-5.1 Codex API 瀹㈡埛绔?- `pyboy` - Game Boy 妯℃嫙鍣?- `python-dotenv` - 鐜鍙橀噺鍔犺浇
- 浠ュ強鍏朵粬渚濊禆...

### 姝ラ 2: 娴嬭瘯 API 杩炴帴

杩愯蹇€熸祴璇曡剼鏈細

```bash
python test_custom_api.py
```

杩欎細锛?- 鉁?妫€鏌?API 瀵嗛挜鍜岀鐐归厤缃?- 鉁?娴嬭瘯涓庤嚜瀹氫箟 API 鐨勮繛鎺?- 鉁?鍙戦€佹祴璇曡姹傞獙璇佷竴鍒囨甯?
### 姝ラ 3: 杩愯瀹屾暣楠岃瘉

```bash
python test_setup.py
```

杩欎細妫€鏌ワ細
- 鉁?Python 鐗堟湰
- 鉁?鎵€鏈変緷璧栨槸鍚﹀畨瑁?- 鉁?API 閰嶇疆
- 鉁?ROM 鏂囦欢
- 鉁?閰嶇疆鏂囦欢
- 鉁?鐩綍缁撴瀯
- 鉁?API 杩炴帴

### 姝ラ 4: 鍚姩 AI 浠ｇ悊锛?
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

## 馃搳 鎮ㄥ皢鐪嬪埌浠€涔?
AI 浠ｇ悊鍚姩鍚庯紝鎮ㄤ細鐪嬪埌锛?
1. **鍒濆鍖栨棩蹇?*锛?   ```
   POKEMON AI AGENT STARTING
   Using custom API endpoint: https://api.ququ233.com/v1
   Initializing emulator...
   Initializing AI agents...
   ```

2. **娓告垙寰幆**锛?   - 姣忎釜鍥炲悎鏄剧ず娓告垙鐘舵€?   - AI 鐨勬帹鐞嗚繃绋?   - 鎵ц鐨勫姩浣?   - 杩涘害鏇存柊

3. **閲岀▼纰?*锛?   ```
   MILESTONE: EARNED BADGE: Boulder Badge (Turn 1523)
   ```

4. **妫€鏌ョ偣**锛?   - 姣?100 鍥炲悎鑷姩淇濆瓨
   - 鏄剧ず杩涘害鎽樿

## 馃幃 娓告垙杩涘害鐩戞帶

### 瀹炴椂鏃ュ織

```bash
# 鏌ョ湅涓绘棩蹇?tail -f logs/Main_*.log

# 鏌ョ湅 AI 鍐崇瓥鏃ュ織
tail -f logs/MainAgent_*.log
```

### 杩涘害鏂囦欢

```bash
# 鏌ョ湅鏈€鏂拌繘搴?cat data/checkpoints/latest/progress.json
```

### 鎴浘

濡傛灉鍚敤浜嗘埅鍥句繚瀛橈細
```bash
ls -lh logs/screenshots/
```

## 鈿欙笍 閰嶇疆閫夐」

缂栬緫 `config.yaml` 鏉ヨ嚜瀹氫箟锛?
### 鏇存敼閫熷害
```yaml
game:
  speed: 0  # 0=鏈€蹇? 1=姝ｅ父閫熷害
```

### 璋冩暣 AI 鍙傛暟
```yaml
ai:
  model: "GPT-5.1 Codex-sonnet-4-5-20250929"
  temperature: 0.7  # 0.0-1.0, 瓒婇珮瓒婃湁鍒涢€犳€?```

### 鍐呭瓨绠＄悊
```yaml
memory:
  max_context_turns: 100  # 姣?N 鍥炲悎鎬荤粨涓€娆?  keep_recent_turns: 20   # 淇濈暀鏈€杩?N 鍥炲悎鐨勫畬鏁寸粏鑺?```

### 鑺傜渷鎴愭湰
```yaml
ai:
  model: "GPT-5.1 Codex-haiku-20250307"  # 浣跨敤鏇翠究瀹滅殑妯″瀷
actions:
  delay_ms: 500  # 澧炲姞寤惰繜锛屽噺灏?API 璋冪敤
```

## 馃搧 閲嶈鏂囦欢浣嶇疆

- **閰嶇疆**: `config.yaml`
- **鐜鍙橀噺**: `.env`
- **鏃ュ織**: `logs/`
- **妫€鏌ョ偣**: `data/checkpoints/`
- **杩涘害鏁版嵁**: `data/checkpoints/*/progress.json`
- **鎴浘**: `logs/screenshots/`

## 馃洜锔?甯歌闂

### Q: API 杩炴帴澶辫触
**A**: 杩愯 `python test_custom_api.py` 妫€鏌ラ厤缃€傞獙璇侊細
- API 绔偣 URL 姝ｇ‘
- API 瀵嗛挜鏈夋晥
- 缃戠粶鍙互璁块棶绔偣

### Q: 妯″瀷鍚嶇О閿欒
**A**: 鎮ㄧ殑鑷畾涔?API 鍙兘浣跨敤涓嶅悓鐨勬ā鍨嬪悕绉般€傚湪 `config.yaml` 涓洿鏀癸細
```yaml
ai:
  model: "your-api-supported-model"
```

### Q: 杩愯閫熷害澶參
**A**: 鍦?`config.yaml` 涓缃細
```yaml
game:
  speed: 0
  headless: true
```

### Q: API 鎴愭湰澶珮
**A**: 浣跨敤鏇翠究瀹滅殑妯″瀷鎴栧鍔犲欢杩燂細
```yaml
ai:
  model: "GPT-5.1 Codex-haiku-20250307"
actions:
  delay_ms: 1000
```

## 馃摎 鏂囨。

瀹屾暣鏂囨。浣嶄簬 `docs/` 鐩綍锛?
- **QUICK_START.md** - 蹇€熷叆闂ㄦ寚鍗?- **ARCHITECTURE.md** - 鎶€鏈灦鏋勮瑙?- **ADVANCED_USAGE.md** - 楂樼骇鐢ㄦ硶鍜岃嚜瀹氫箟
- **TROUBLESHOOTING.md** - 鏁呴殰鎺掗櫎鎸囧崡
- **CUSTOM_API_SETUP.md** - 鑷畾涔?API 閰嶇疆璇存槑

## 馃挕 鎻愮ず

1. **鐩戞帶鎴愭湰**: 瀹氭湡妫€鏌?API 浣跨敤鎯呭喌
2. **淇濆瓨妫€鏌ョ偣**: 椤圭洰浼氳嚜鍔ㄤ繚瀛橈紝浣嗘偍鍙互鎵嬪姩澶囦唤 `data/checkpoints/`
3. **璋冩暣绛栫暐**: 缂栬緫 `src/agents/main_agent.py` 涓殑绯荤粺鎻愮ず璇嶆潵鏀瑰彉 AI 琛屼负
4. **瑙傚療鏃ュ織**: 鏌ョ湅鏃ュ織浜嗚В AI 鐨勫喅绛栬繃绋?
## 馃幆 棰勬湡鎬ц兘

鏍规嵁 Gemini 2.5 Pro 鐨勫熀鍑嗘祴璇曪細

- **绗竴涓窘绔?*: ~10-50 灏忔椂
- **瀹屾垚娓告垙**: 400-800 灏忔椂
- **Token 浣跨敤**: 鏁扮櫨涓?- **鎴愭湰**: 鍙栧喅浜庢偍鐨?API 瀹氫环

**娉ㄦ剰**: 杩欓渶瑕佽繛缁繍琛屻€傛偍鍙互闅忔椂鍋滄锛圕trl+C锛夊苟浠庢渶鍚庣殑妫€鏌ョ偣鎭㈠銆?
## 鉁?寮€濮嬬帺鍚э紒

涓€鍒囧氨缁紒杩愯浠ヤ笅鍛戒护寮€濮嬶細

```bash
python main.py
```

瑙傜湅 AI 鑷富鐜?Pokemon Red锛侌煄煠?
## 馃摓 闇€瑕佸府鍔╋紵

- 鏌ョ湅 `docs/TROUBLESHOOTING.md`
- 妫€鏌ユ棩蹇楁枃浠跺湪 `logs/`
- 杩愯 `python test_setup.py` 璇婃柇闂

---

**绁濇偍鐨?AI 浠ｇ悊鏃呯▼鎰夊揩锛?* 馃殌
