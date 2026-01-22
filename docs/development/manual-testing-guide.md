# Phase 6A Mode System - Manual Testing Guide

## 測試環境準備

```bash
# 確保在專案根目錄
cd /Users/liuyi/projects/simple_orchestrator

# 啟動虛擬環境
source .venv/bin/activate
```

## 測試 1: ASK 模式（Read-Only）

### 步驟 1: 設定為 ASK 模式

編輯 `config/default.yaml`，將第 8 行改為：
```yaml
mode: "ask"  # Current execution mode: ask, plan, execute
```

### 步驟 2: 啟動 orchestrator

```bash
orchestrator chat
```

### 步驟 3: 測試允許的操作

在 orchestrator 提示符下輸入：

```
讀取 src/orchestrator/modes/models.py 檔案，並說明有哪些執行模式
```

**預期結果**：
- ✅ LLM 可以使用 file_read 工具
- ✅ 成功讀取檔案並回答問題

### 步驟 4: 測試被禁止的操作

```
建立一個新檔案 hello.txt，內容是 "Hello World"
```

**預期結果**：
- ❌ LLM 無法使用 file_write 工具（工具列表中沒有此工具）
- ✅ LLM 會說明在 ASK 模式下無法寫檔案
- ✅ LLM 可能建議切換到 EXECUTE 模式

試試這個：
```
執行 ls -la 指令
```

**預期結果**：
- ❌ LLM 無法使用 bash 工具
- ✅ LLM 解釋無法執行指令

---

## 測試 2: PLAN 模式（Planning）

### 步驟 1: 設定為 PLAN 模式

編輯 `config/default.yaml`，將第 8 行改為：
```yaml
mode: "plan"  # Current execution mode: ask, plan, execute
```

### 步驟 2: 重新啟動 orchestrator

```bash
orchestrator chat
```

### 步驟 3: 測試任務分解

```
規劃如何實作一個新的 Tool：DatabaseQueryTool，用於執行 SQL 查詢
```

**預期結果**：
- ✅ LLM 可以使用 task_decompose 工具創建子任務
- ✅ LLM 可以創建 TODO 列表
- ✅ LLM 可以讀取現有檔案作為參考
- ❌ LLM 無法執行 bash 指令
- ❌ LLM 無法寫入檔案

### 步驟 4: 測試規劃能力

```
建立一個詳細的實作計畫，包含所有步驟和依賴關係
```

**預期結果**：
- ✅ 使用 todo_list 工具創建結構化計畫
- ✅ 使用 task_decompose 創建任務層級
- ✅ 說明實作步驟但不實際執行

---

## 測試 3: EXECUTE 模式（Full Access）

### 步驟 1: 設定為 EXECUTE 模式

編輯 `config/default.yaml`，將第 8 行改為：
```yaml
mode: "execute"  # Current execution mode: ask, plan, execute
```

### 步驟 2: 重新啟動 orchestrator

```bash
orchestrator chat
```

### 步驟 3: 測試完整功能

```
建立一個測試檔案 test_execute.txt，內容是當前時間，然後用 cat 顯示內容
```

**預期結果**：
- ✅ LLM 可以使用 file_write 工具
- ✅ LLM 可以使用 bash 工具
- ✅ 檔案被成功建立並顯示

### 步驟 4: 測試工具組合

```
1. 讀取 src/orchestrator/modes/models.py
2. 統計有多少行程式碼
3. 建立一個總結報告 mode_analysis.txt
```

**預期結果**：
- ✅ 所有工具都可用
- ✅ 完整執行所有步驟

---

## 測試 4: 模式切換（未來 Phase 6C 功能）

當 Phase 6C 完成後，可以在 chat 中動態切換：

```bash
orchestrator chat --mode ask
> /mode execute    # 切換到 execute 模式
> /mode plan       # 切換到 plan 模式
> /session         # 顯示當前 session 資訊
```

---

## 驗證工具過濾

### 檢查 ASK 模式的工具列表

在 ASK 模式下，執行 orchestrator 並在系統提示中查看可用工具。

**預期工具列表**：
- ✅ file_read
- ✅ web_fetch
- ✅ todo_list
- ❌ bash
- ❌ file_write
- ❌ file_delete
- ❌ task_decompose
- ❌ subagent_spawn

### 檢查 PLAN 模式的工具列表

**預期工具列表**：
- ✅ file_read
- ✅ web_fetch
- ✅ todo_list
- ✅ task_decompose
- ❌ bash
- ❌ file_write
- ❌ file_delete
- ❌ subagent_spawn

### 檢查 EXECUTE 模式的工具列表

**預期工具列表**：
- ✅ 所有工具都可用

---

## Debug 模式測試

如果想看到更多內部資訊，可以啟用 debug 模式：

編輯 `config/default.yaml`：
```yaml
orchestrator:
  debug: true  # 啟用 debug 模式
```

然後在 logs 中可以看到：
- 工具過濾過程
- Mode-specific 提示注入
- 當前執行模式

---

## 快速驗證腳本

```bash
# 測試 ASK 模式
echo 'mode: "ask"' > config/test_mode.yaml
cat config/default.yaml | sed 's/mode: "execute"/mode: "ask"/' > config/temp.yaml
mv config/temp.yaml config/default.yaml

orchestrator chat
# 輸入：建立檔案 test.txt
# 預期：LLM 說明無法執行

# 測試 EXECUTE 模式
sed -i '' 's/mode: "ask"/mode: "execute"/' config/default.yaml
orchestrator chat
# 輸入：建立檔案 test.txt
# 預期：檔案被成功建立
```

---

## 常見問題

### Q: LLM 沒有說明模式限制？
A: 檢查系統提示是否正確注入了 mode-specific instructions。查看 logs：
```bash
tail -f .orchestrator/logs/orchestrator.log | grep -A 10 "CURRENT MODE"
```

### Q: 工具仍然可用（即使應該被禁止）？
A: 確認 ModeManager 正確初始化：
```bash
grep "Mode manager initialized" .orchestrator/logs/orchestrator.log
```

### Q: 如何確認當前模式？
A: 查看啟動日誌：
```bash
grep "Mode manager initialized" .orchestrator/logs/orchestrator.log
```

輸出應該是：
```
Mode manager initialized in ask mode
```
或
```
Mode manager initialized in plan mode
```
或
```
Mode manager initialized in execute mode
```

---

## 成功標準

Phase 6A 測試成功的標準：

1. ✅ ASK 模式下，只有 file_read, web_fetch, todo_list 可用
2. ✅ PLAN 模式下，額外增加 task_decompose
3. ✅ EXECUTE 模式下，所有工具可用
4. ✅ LLM 在受限模式下會說明無法執行被禁止的操作
5. ✅ Mode-specific 提示正確注入到系統提示中
6. ✅ 日誌顯示正確的模式初始化訊息
