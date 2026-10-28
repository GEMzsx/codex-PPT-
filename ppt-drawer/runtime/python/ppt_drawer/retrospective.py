"""Persist evidence-backed stage retrospectives and verified project rules."""
from pathlib import Path
import uuid

from .storage import WorkflowError, read_json, utc_now, write_json


def record_retro(run, stage, payload=None, outcome=None):
    payload = payload or {}
    if not isinstance(payload,dict):
        raise WorkflowError("Retrospective input must be an object")
    findings = payload.get("findings", payload.get("observations", []))
    if not isinstance(findings,list):
        raise WorkflowError("Retrospective findings must be a list")
    for finding in findings:
        if not isinstance(finding,dict) or not finding.get("observation") or not finding.get("evidence"):
            raise WorkflowError("Retrospective findings need observation and evidence")
        if finding.get("status", "proposed") not in {"proposed","applied","verified"}:
            raise WorkflowError("Retrospective status must be proposed, applied or verified")
        if finding.get("status") == "verified" and not finding.get("validation"):
            raise WorkflowError("Verified improvement needs validation evidence")
        if finding.get("status") == "applied" and not finding.get("changed_paths"):
            raise WorkflowError("Applied improvement needs changed_paths")
        for changed in finding.get("changed_paths",[]):
            path = Path(changed)
            if not path.is_absolute():
                path = run.project / path
            if not path.resolve().is_relative_to(run.project) or not path.exists():
                raise WorkflowError("Improvement changed_paths must identify existing project files")
    state = run.state()
    record = {"id":uuid.uuid4().hex,"created_at":utc_now(),"run":run.run,"stage":stage,"outcome":outcome or payload.get("outcome","recorded"),"plan_sha256":None,"findings":findings,"summary":payload.get("summary", "No new reusable improvement identified; existing checks and evidence retained.")}
    from .storage import file_hash
    if (run.root / "plan.json").is_file():
        record["plan_sha256"] = file_hash(run.root / "plan.json")
    artifact = state.get("full" if stage=="full" else "sample")
    record["artifact_sha256"] = artifact.get("sha256") if artifact else None
    path = run.root / "retrospectives" / (record["created_at"].replace(":","-") + "-" + record["id"][:8] + ".json")
    write_json(path,record)
    lines = [f"# {stage} 阶段复盘", "", f"结果：{record['outcome']}", f"时间：{record['created_at']}", "", record["summary"], ""]
    for finding in findings:
        lines += ["## " + str(finding["observation"]), "", "依据：" + str(finding["evidence"]), "动作：" + str(finding.get("action","待确定")), "状态：" + str(finding.get("status","proposed")), "验证：" + str(finding.get("validation","待验证")), ""]
    path.with_suffix(".md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    improvements_path = run.project / ".ppt-assistant" / "improvements.json"
    improvements = read_json(improvements_path,[])
    for finding in findings:
        if finding.get("scope")=="project" and finding.get("status")=="verified" and finding.get("rule"):
            entry = {"rule":finding["rule"],"evidence":finding["evidence"],"validation":finding["validation"],"run":run.run,"retro_id":record["id"]}
            if not any(i["rule"]==entry["rule"] for i in improvements):
                improvements.append(entry)
    if improvements:
        write_json(improvements_path,improvements)
    return record


def auto_retro(run, stage, outcome, evidence):
    return record_retro(run,stage,{"summary":"阶段结果与检查证据已保存；未发现需要自动修改的通用规则。", "findings":[{"observation":"阶段产物与当前方案和来源版本已核对" if outcome!="failed" else "阶段制作失败，保留失败证据供修复", "evidence":str(evidence),"action":"记录现有检查结果" if outcome!="failed" else "根据错误定位后重试", "status":"verified" if outcome!="failed" else "proposed", **({"validation":"来源、方案、页面数量与产物指纹检查完成"} if outcome!="failed" else {})}]},outcome)
