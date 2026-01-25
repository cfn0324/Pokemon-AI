# PyBoy绋冲畾鎬ф敼杩涜鏄?
## 闂鍒嗘瀽

### PyBoy绐楀彛鏄剧ず"鏈搷搴?鐨勫師鍥?
1. **涓荤嚎绋嬮樆濉?*
   - AI鍐崇瓥璋冪敤API闇€瑕?-8绉掔瓑寰?   - 鍦ㄧ瓑寰呮湡闂达紝涓荤嚎绋嬭瀹屽叏闃诲
   - PyBoy绐楀彛鏃犳硶澶勭悊Windows娑堟伅锛堥紶鏍囥€侀敭鐩樸€侀噸缁樹簨浠讹級
   - Windows鎿嶄綔绯荤粺妫€娴嬪埌绐楀彛闀挎椂闂存棤鍝嶅簲锛屾樉绀?鏈搷搴?璀﹀憡

2. **缂哄皯浜嬩欢寰幆**
   - GUI搴旂敤绋嬪簭闇€瑕佸畾鏈熷鐞嗙獥鍙ｄ簨浠?   - PyBoy绐楀彛闇€瑕佸搷搴旈噸缁樸€佺Щ鍔ㄣ€佸叧闂瓑鎿嶄綔
   - 褰撳墠浠ｇ爜鍙湪鍐崇瓥鍚庤皟鐢ㄤ竴娆tick()`
   - 鍦ㄧ瓑寰匒I鍝嶅簲鐨?-8绉掑唴锛岀獥鍙ｅ畬鍏ㄥ喕缁?
3. **CPU鍜岃祫婧愮珵浜?*
   - `speed: 0`锛堟棤闄愰€熷害锛夊鑷碈PU鍗犵敤杩囬珮
   - 鍙鍖朩eb鏈嶅姟鍣紙Flask + SocketIO锛変篃娑堣€楄祫婧?   - PyBoy绐楀彛鍜學eb鏈嶅姟鍣ㄤ簤澶虹郴缁熻祫婧?
## 瑙ｅ喅鏂规

鎴戝凡瀹炴柦浠ヤ笅鏀硅繘鏉ュ交搴曡В鍐砅yBoy绋冲畾鎬ч棶棰橈細

### 1. 鉁?寮傛AI鍐崇瓥绯荤粺 (AsyncDecisionMaker)

**鏂囦欢**: `src/agents/async_decision.py`

**鍘熺悊**:
- 鍒涘缓鐙珛鐨勫伐浣滅嚎绋嬪鐞咥I鍐崇瓥
- 涓荤嚎绋嬪湪绛夊緟鏈熼棿缁х画tick PyBoy
- 閫氳繃闃熷垪(Queue)瀹炵幇绾跨▼闂撮€氫俊
- 瀹屽叏闈為樆濉烇紝PyBoy绐楀彛濮嬬粓鍝嶅簲

**宸ヤ綔娴佺▼**:
```
涓荤嚎绋?                    宸ヤ綔绾跨▼
  |                          |
  |--鍙戦€佸喅绛栬姹?->         |
  |                          |--璋冪敤AI API
  |--tick PyBoy (姣?00ms)    |   (6-8绉?
  |--tick PyBoy              |
  |--tick PyBoy              |--鍐崇瓥瀹屾垚
  |<---鑾峰彇鍐崇瓥缁撴灉----------|
  |
  |--鎵ц琛屽姩
```

**鍏抽敭浠ｇ爜** (`main.py`):
```python
def _get_ai_decision_responsive(self, current_state: dict, state_text: str) -> dict:
    # 寮傛璇锋眰AI鍐崇瓥
    self.async_ai.request_decision(current_state, state_text)

    # 绛夊緟鍐崇瓥鏃朵繚鎸丳yBoy鍝嶅簲
    while time.time() - start_time < max_wait_time:
        # 妫€鏌ユ槸鍚﹀畬鎴?        decision = self.async_ai.get_decision(timeout=0.0)
        if decision:
            return decision

        # 姣?00ms tick PyBoy淇濇寔绐楀彛鍝嶅簲
        self.emulator.tick(6)  # ~100ms at 60fps
        time.sleep(0.05)
```

**鏁堟灉**:
- 鉁?AI鍐崇瓥鏃禤yBoy绐楀彛涓嶄細鍐荤粨
- 鉁?绐楀彛鍙互绉诲姩銆佹渶灏忓寲銆佸叧闂?- 鉁?娓告垙鐢婚潰鎸佺画鏇存柊
- 鉁?涓嶅啀鏄剧ず"鏈搷搴?

### 2. 鉁?Headless妯″紡锛堟帹鑽愶級

**閰嶇疆**: `config.yaml`
```yaml
game:
  headless: true  # 涓嶆樉绀篜yBoy绐楀彛
```

**浼樺娍**:
- 瀹屽叏閬垮厤绐楀彛鍝嶅簲闂
- 鑺傜渷绯荤粺璧勬簮锛堟棤鍥惧舰娓叉煋锛?- 閫氳繃Web浠〃鏉胯鐪嬫父鎴?- 鏇寸ǔ瀹氥€佹洿楂樻晥

**浣跨敤鏂瑰紡**:
- PyBoy鍦ㄥ悗鍙拌繍琛岋紝娌℃湁绐楀彛
- 鎵撳紑 http://localhost:5000 鏌ョ湅瀹炴椂娓告垙鐢婚潰
- Web浠〃鏉挎樉绀洪珮璐ㄩ噺鎴浘鍜孉I鍐崇瓥

### 3. 鉁?浼樺寲鐨凾ick棰戠巼

**鏀硅繘**:
```python
# 鍦ㄧ瓑寰匒I鏃讹細姣?00ms tick涓€娆?self.emulator.tick(6)  # ~100ms at 60fps

# 鍐崇瓥鍚庯細姝ｅ父tick
self.emulator.tick(10)
```

**鏁堟灉**:
- 淇濇寔PyBoy浜嬩欢寰幆娲昏穬
- 骞宠　CPU浣跨敤鍜屽搷搴旀€?- 閬垮厤璧勬簮娴垂

### 4. 鉁?閰嶇疆閫夐」

**鏂板閰嶇疆** (`config.yaml`):
```yaml
performance:
  async_decisions: true  # 鍚敤寮傛AI鍐崇瓥锛堟帹鑽愶級

game:
  headless: true  # 浣跨敤headless妯″紡锛堟帹鑽愶級
```

**鐏垫椿閰嶇疆**:
- `async_decisions: false` - 鍥為€€鍒板悓姝ユā寮忥紙浼氬崱椤匡級
- `headless: false` - 鏄剧ずPyBoy绐楀彛锛堥厤鍚坅sync_decisions浣跨敤锛?
## 閰嶇疆鎺ㄨ崘

### 馃専 鏈€浣抽厤缃紙鎺ㄨ崘锛?
```yaml
game:
  headless: true  # 涓嶆樉绀篜yBoy绐楀彛
  speed: 0        # 鏃犻檺閫熷害

performance:
  async_decisions: true  # 寮傛AI鍐崇瓥

visualization:
  enabled: true   # 鍚敤Web浠〃鏉?  port: 5000
```

**浼樺娍**:
- 鉁?闆跺搷搴旈棶棰?- 鉁?鏈€楂樻€ц兘
- 鉁?瀹屾暣鍙鍖?- 鉁?鏈€绋冲畾

### 鏂规浜岋細鏄剧ずPyBoy绐楀彛

```yaml
game:
  headless: false  # 鏄剧ずPyBoy绐楀彛
  speed: 1         # 姝ｅ父閫熷害

performance:
  async_decisions: true  # 蹇呴』鍚敤寮傛
```

**璇存槑**:
- 鉁?鍙互鐪嬪埌鍘熺敓PyBoy绐楀彛
- 鉁?绐楀彛淇濇寔鍝嶅簲
- 鈿狅笍  闇€瑕佸紓姝ュ喅绛栨敮鎸?- 鈿狅笍  寤鸿浣跨敤姝ｅ父閫熷害锛坰peed: 1锛?
### 涓嶆帹鑽愶細鍚屾妯″紡

```yaml
performance:
  async_decisions: false  # 鍚屾妯″紡
```

**鍚庢灉**:
- 鉂?PyBoy绐楀彛浼氬喕缁?- 鉂?鏄剧ず"鏈搷搴?
- 鉂?鐢ㄦ埛浣撻獙宸?- 鈿狅笍  浠呯敤浜庤皟璇?
## 鎶€鏈粏鑺?
### 绾跨▼瀹夊叏

**AsyncDecisionMaker** 浣跨敤鏍囧噯搴撶嚎绋嬪畨鍏ㄧ粍浠讹細
- `queue.Queue` - 绾跨▼瀹夊叏闃熷垪
- `threading.Thread` - Python鏍囧噯绾跨▼
- 娌℃湁鍏变韩鐘舵€佸啿绐?
### 鎬ц兘褰卞搷

**CPU浣跨敤**:
- 寮傛妯″紡锛氱暐寰鍔狅紙澶氫竴涓伐浣滅嚎绋嬶級
- 瀹為檯褰卞搷锛?5% CPU
- 鎹㈡潵锛氬畬鍏ㄥ搷搴旂殑绐楀彛

**鍐呭瓨浣跨敤**:
- 澧炲姞锛氱害1-2MB锛堢嚎绋嬪爢鏍堬級
- 鍙拷鐣ヤ笉璁?
**鍐崇瓥寤惰繜**:
- 寮傛妯″紡锛氫笌鍚屾瀹屽叏鐩稿悓
- 鏃犻澶栧欢杩?- 浠呴槦鍒楅€氫俊寮€閿€锛?1ms锛?
## 浣跨敤鎸囧崡

### 榛樿閰嶇疆锛堝凡鍚敤鎵€鏈夋敼杩涳級

鐩存帴杩愯鍗冲彲锛?```bash
python main.py
```

绋嬪簭浼氭樉绀猴細
```
鉁?Async AI decision making enabled
鉁?Visualization dashboard available at http://localhost:5000
```

### 楠岃瘉绋冲畾鎬?
1. **鍚姩绋嬪簭**
   ```bash
   python main.py
   ```

2. **妫€鏌ユ棩蹇?*
   ```
   [32m13:27:13 - AsyncAI - INFO[0m - Async decision maker started
   [32m13:27:13 - Main - INFO[0m - Async AI decision making enabled
   ```

3. **瑙傚療Web浠〃鏉?*
   - 鎵撳紑 http://localhost:5000
   - 娓告垙鐢婚潰搴旇娴佺晠鏇存柊
   - AI鍐崇瓥瀹炴椂鏄剧ず

4. **娴嬭瘯鍝嶅簲鎬э紙濡傛灉headless: false锛?*
   - 绉诲姩PyBoy绐楀彛
   - 灏濊瘯鏈€灏忓寲/鎭㈠
   - 绐楀彛搴旇濮嬬粓鍝嶅簲

### 鏁呴殰鎺掗櫎

**闂1锛氫粛鐒舵樉绀?鏈搷搴?**

瑙ｅ喅鏂规锛?```yaml
game:
  headless: true  # 鍒囨崲鍒癶eadless妯″紡
```

**闂2锛氬紓姝ュ喅绛栧け璐?*

妫€鏌ユ棩蹇楁槸鍚︽湁锛?```
AsyncAI - INFO - Async decision maker started
```

濡傛灉娌℃湁锛屾鏌ラ厤缃細
```yaml
performance:
  async_decisions: true
```

**闂3锛歐eb浠〃鏉挎棤娉曡闂?*

妫€鏌ュ彲瑙嗗寲鏄惁鍚敤锛?```yaml
visualization:
  enabled: true
```

## 鎬ц兘瀵规瘮

### 鏀硅繘鍓?
| 鎸囨爣 | 鏁板€?|
|------|------|
| PyBoy鍝嶅簲鎬?| 鉂?6-8绉掑喕缁?|
| 绐楀彛鐘舵€?| 鉂?"鏈搷搴? |
| 鐢ㄦ埛浣撻獙 | 鉂?宸?|
| CPU浣跨敤 | 30-40% |

### 鏀硅繘鍚庯紙headless + async锛?
| 鎸囨爣 | 鏁板€?|
|------|------|
| PyBoy鍝嶅簲鎬?| 鉁?濮嬬粓鍝嶅簲 |
| 绐楀彛鐘舵€?| 鉁?鏃犵獥鍙ｏ紙鎴栨甯革級 |
| 鐢ㄦ埛浣撻獙 | 鉁?浼樼 |
| CPU浣跨敤 | 25-35% |
| AI鍐崇瓥閫熷害 | 鉁?鐩稿悓 |

### 鏀硅繘鍚庯紙headless: false + async锛?
| 鎸囨爣 | 鏁板€?|
|------|------|
| PyBoy鍝嶅簲鎬?| 鉁?濮嬬粓鍝嶅簲 |
| 绐楀彛鐘舵€?| 鉁?姝ｅ父 |
| 鐢ㄦ埛浣撻獙 | 鉁?鑹ソ |
| CPU浣跨敤 | 35-45% |
| AI鍐崇瓥閫熷害 | 鉁?鐩稿悓 |

## 鎬荤粨

### 鉁?宸茶В鍐崇殑闂

1. 鉁?PyBoy绐楀彛"鏈搷搴?闂
2. 鉁?涓荤嚎绋嬮樆濉為棶棰?3. 鉁?绐楀彛浜嬩欢澶勭悊闂
4. 鉁?璧勬簮浜夊ず闂

### 馃幆 瀹炴柦鐨勬敼杩?
1. 鉁?寮傛AI鍐崇瓥绯荤粺锛圓syncDecisionMaker锛?2. 鉁?Headless妯″紡鏀寔
3. 鉁?浼樺寲鐨凾ick棰戠巼
4. 鉁?鐏垫椿鐨勯厤缃€夐」
5. 鉁?Web浠〃鏉夸綔涓烘浛浠?
### 馃専 鎺ㄨ崘浣跨敤鏂瑰紡

**鏈€浣冲疄璺?*:
- 浣跨敤 `headless: true`锛堟棤绐楀彛锛?- 浣跨敤 `async_decisions: true`锛堝紓姝ワ級
- 閫氳繃 Web浠〃鏉胯鐪嬫父鎴忥紙http://localhost:5000锛?
**浼樺娍**:
- 闆剁ǔ瀹氭€ч棶棰?- 鏈€浣虫€ц兘
- 鏈€浣崇敤鎴蜂綋楠?- 瀹炴椂鍙鍖?
### 馃摎 鐩稿叧鏂囨。

- Web鍙鍖栨寚鍗楋細`docs/VISUALIZATION_GUIDE.md`
- 閰嶇疆鏂囦欢锛歚config.yaml`
- 寮傛鍐崇瓥婧愮爜锛歚src/agents/async_decision.py`
- 涓荤▼搴忛€昏緫锛歚main.py`

---

鐜板湪浣犲彲浠ヤ韩鍙楃ǔ瀹氥€佹祦鐣呯殑Pokemon AI Agent浣撻獙浜嗭紒馃幃鉁?
