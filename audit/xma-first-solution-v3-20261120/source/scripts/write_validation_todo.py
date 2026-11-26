"""Record drained validation work without resuming or modifying the campaign."""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime
import json
from pathlib import Path
import sys


def write(folder: Path, stage: str = "任务1实施中"):
    root = Path(__file__).resolve().parents[1]
    state = json.loads((folder / "state.json").read_text(encoding="utf-8"))
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    defer = json.loads((folder / "defer.json").read_text(encoding="utf-8"))
    if state.get("status") != "finished" or defer.get("status") != "finished":
        raise RuntimeError("Wait until the defer controller and original supervisor have both finalized")
    unstarted = [j for j in manifest["jobs"] if not state["jobs"][j["id"]].get("attempt")]
    executed = [j for j in manifest["jobs"] if state["jobs"][j["id"]].get("attempt")]
    lines = ["# 项目待办清单", "", f"更新时间：{datetime.now().astimezone().isoformat(timespec='seconds')}", "",
             "## 算法验证：已暂缓，不自动恢复", "", f"批次：`{folder.name}`；原批次：`{manifest.get('continuation_of', '')}`。",
             f"停队状态：**{defer['status']}**；当前运行任务 0；未执行 {len(unstarted)} 项；本续测批次已执行 {len(executed)} 项。",
             f"实际状态：`{json.dumps(dict(Counter(x['status'] for x in state['jobs'].values())),ensure_ascii=False)}`。",
             "原冻结代码、数据及截止时间未变。STOP 表示主动停队，cancelled 且无 attempt 的条目属于未执行，不表示算法失败。",
             f"原批次保留 {len(manifest.get('carried_forward_results', []))} 份既有证据；本轮状态只陈述执行情况，尚未给出完整科学复核结论。", "",
             "### 未执行、待恢复", "", "每项沿用本批次的单线程、独占计时或正确性并行设置。参数列保存完整 config（含种子与候选粒度）；算法及规模见名称。", "",
             "| 任务 ID | 名称 / 算法 / 规模 | 参数与种子 | 时限 / 求解时限 / 内存 |", "|---|---|---|---|"]
    for job in unstarted:
        config = json.dumps(job["config"], ensure_ascii=False, separators=(",", ":")).replace("|", "\\|")
        lines.append(f"| `{job['id']}` | {job['name']} | `{config}` | {job['wall_seconds']}s / {job['solver_seconds']}s / {job['memory_gib']}GiB |")
    lines += ["", "恢复入口（后续明确恢复时使用；本轮不执行）：", "", "```powershell",
              f'& "{sys.executable}" scripts/validation_campaign.py launch --continue-from "{folder}" --profile long', "```", "",
              "续测机制创建新批次，仅选未完成或受限项目，复用原冻结算法、数据及已通过结果。原批次 resume 保留原截止时间；超过原截止时间时不要用 resume 重新计时。", "",
              "### 已执行、待复核", "", "completed 仅表示测量完成；passed 表示该测试自身断言通过；资源受限、未收敛不属于未执行。最终可靠性结论仍需核查独立审计、上下界及参考解。", "",
              "| 任务 ID | 名称 | 执行状态 | 证据 |", "|---|---|---|---|"]
    for job in executed:
        row = state["jobs"][job["id"]]
        relative = (folder / "jobs" / job["id"] / "result.json").relative_to(root).as_posix()
        lines.append(f"| `{job['id']}` | {job['name']} | `{row['status']}` | [result.json]({relative}) |")
    lines += ["", "## 当前开发任务", "", f"当前阶段：**{stage}**。", "",
              "- [x] 刷新长测状态；当前任务结束后停止派发；保存结果和未执行清单。",
              "- [ ] 任务1：新建独立 Workbench v3，保留 v2 与后端；完成三个工作区及保存、校验、运行、分析闭环。",
              "- [ ] 任务1验收：AIR/厦航、异常与并发、事件恢复、浅深色及 1440/1024/390、隔离和 v2 兼容。",
              "- [ ] 任务2：任务1验收后，核验并固定安装 UI/UX Pro Max，优化共享组件与设计变量。",
              "- [ ] 任务2验收：保留前后截图、改进记录并完成相关回归。",
              "- [ ] 后续：用户安排恢复算法验证后再启动；完成后复核证据并形成分层结论。", ""]
    (root / "tudulist.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Recorded {len(unstarted)} unstarted and {len(executed)} executed tasks.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--folder", type=Path, required=True)
    parser.add_argument("--stage", default="任务1实施中")
    args = parser.parse_args()
    write(args.folder.resolve(), args.stage)
