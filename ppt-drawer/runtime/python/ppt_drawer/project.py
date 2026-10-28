"""Project state and source-bound planning operations."""
from pathlib import Path
from urllib.parse import urlsplit
import uuid

from .materials import discover, material_record
from .planning import check_refs, validate_plan, validate_supplement_pages
from .storage import WorkflowError, invalidate, load_state, read_json, run_dir, utc_now, write_json


class ProjectRun:
    def __init__(self, project, run):
        self.project = Path(project).resolve()
        self.root = run_dir(project, run)
        self.run = run

    def init(self, title, brief=None):
        if (self.root / "state.json").exists():
            raise WorkflowError("run already exists; choose another --run or use status")
        self.project.mkdir(parents=True, exist_ok=True)
        state = {"version":1,"run":self.run,"project":str(self.project),"title":title,"stage":"collecting","created_at":utc_now(),"approval":None,"sample":None,"full":None}
        write_json(self.root / "state.json", state)
        for name in ("materials", "knowledge", "supplements"):
            write_json(self.root / (name+".json"), [])
        if brief is not None:
            write_json(self.root / "brief.json", brief)
        return self.status()

    def state(self):
        return load_state(self.root)

    def save(self, state):
        state["updated_at"] = utc_now()
        write_json(self.root / "state.json", state)

    def records(self, name):
        return read_json(self.root / (name+".json"), [])

    def known_sources(self):
        return {m["id"] for m in self.records("materials") if m["status"] in {"ready","partial"}} | {s["id"] for s in self.records("supplements")}

    def update_records(self, name, records):
        existing = self.records(name)
        if records != existing:
            write_json(self.root / (name+".json"), records)
            state = self.state()
            invalidate(state)
            self.save(state)

    def ingest(self, paths):
        records = self.records("materials")
        for path in discover(paths):
            record = material_record(path)
            records = [m for m in records if m["id"] != record["id"]] + [record]
        self.update_records("materials", sorted(records,key=lambda m:m["path"]))
        return self.status()

    def knowledge(self, entries):
        if isinstance(entries,dict):
            entries = entries.get("knowledge", entries.get("entries"))
        if not isinstance(entries,list):
            raise WorkflowError("knowledge input must be a list or an entries object")
        known = self.known_sources()
        existing = self.records("knowledge")
        for item in entries:
            if not isinstance(item,dict) or not isinstance(item.get("id"),str) or not item["id"] or not isinstance(item.get("text"),str) or not item["text"].strip():
                raise WorkflowError("knowledge entries require id and text")
            refs = item.get("source_ids", [])
            if item.get("kind") != "gap" and not refs:
                raise WorkflowError("knowledge requires source_ids; use kind gap for an explicit missing fact")
            check_refs(refs, known, item["id"])
            if item.get("kind") == "project_result":
                local = {m["id"] for m in self.records("materials")}
                if not any(ref in local for ref in refs):
                    raise WorkflowError("project_result requires a project material source")
            existing = [entry for entry in existing if entry["id"] != item["id"]] + [item]
        self.update_records("knowledge", existing)
        return self.status()

    def supplement(self, entries):
        if isinstance(entries,dict):
            entries = entries.get("supplements", entries.get("entries"))
        if not isinstance(entries,list):
            raise WorkflowError("supplement input must be a list")
        existing = self.records("supplements")
        plan = read_json(self.root / "plan.json")
        for raw in entries:
            if not isinstance(raw,dict):
                raise WorkflowError("supplement entries must be objects")
            item = dict(raw)
            for field in ("id","knowledge","url","purpose"):
                if not isinstance(item.get(field),str) or not item[field].strip():
                    raise WorkflowError("supplement requires id, knowledge, url and purpose")
            url = urlsplit(item["url"])
            if url.scheme not in {"http","https"} or not url.hostname or url.username or url.password:
                raise WorkflowError("supplement URL must be an HTTP(S) source without credentials")
            if item["id"] in {m["id"] for m in self.records("materials")}:
                raise WorkflowError("supplement ID conflicts with a project source")
            item.setdefault("retrieved_at", utc_now())
            item.setdefault("slide_ids", [])
            existing = [s for s in existing if s["id"] != item["id"]] + [item]
        validate_supplement_pages(existing, plan)
        self.update_records("supplements", existing)
        self.write_supplements()
        return self.status()

    def write_supplements(self):
        lines = ["# 补充知识清单", "", "仅列本次联网增加的知识；项目自身结果见项目材料。", ""]
        for item in self.records("supplements"):
            lines.extend(["## " + item["id"], "", item["knowledge"], "", "来源：" + item["url"], "用途：" + item["purpose"], "页面：" + (", ".join(item.get("slide_ids",[])) or "尚未用于页面"), "获取时间：" + item["retrieved_at"], ""])
        if not self.records("supplements"):
            lines.append("本阶段没有登记联网补充。")
        (self.root / "supplemental-knowledge.md").write_text("\n".join(lines)+"\n",encoding="utf-8")

    def plan(self, plan, base):
        plan = validate_plan(plan, base, self.known_sources())
        validate_supplement_pages(self.records("supplements"), plan)
        old = read_json(self.root / "plan.json")
        if old != plan:
            write_json(self.root / "plan.json", plan)
            state = self.state()
            invalidate(state)
            state["sample"] = None
            state["full"] = None
            self.save(state)
        lines = ["# " + plan["title"], "", "整稿大纲；审阅确认后制作整稿。", ""]
        for i, slide in enumerate(plan["slides"],1):
            lines.extend([f"## {i}. {slide['title']} ({slide['id']})", "", "版式：" + slide["layout"], "核心内容：" + slide["takeaway"], "来源：" + ", ".join(slide.get("source_ids",[])), ""])
        (self.root / "outline.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
        self.write_supplements()
        return self.status()

    def status(self):
        state = self.state()
        from .artifacts import approval_error
        error = approval_error(self,state)
        retros = [read_json(p) for p in sorted((self.root/"retrospectives").glob("*.json"))]
        handoffs = [read_json(p) for p in sorted((self.root/"handoffs").glob("*.json"))]
        improvements = read_json(self.project/".ppt-assistant"/"improvements.json",[])
        return {**state,"run_dir":str(self.root),"materials":self.records("materials"),"knowledge":self.records("knowledge"),"supplements":self.records("supplements"),"approval_valid":error is None,"approval_error":error,"retrospectives":retros,"handoffs":handoffs,"improvements":improvements}

    def handoff(self, role, agent_id, inputs, outputs, status, summary):
        self.state()
        if not role.strip() or not agent_id.strip():
            raise WorkflowError("handoff requires role and actual host agent_id")
        in_paths = [Path(p).resolve() for p in inputs]
        out_paths = [Path(p).resolve() for p in outputs]
        if any(not p.exists() for p in in_paths):
            raise WorkflowError("handoff inputs must exist")
        if any(not p.is_relative_to(self.project) for p in out_paths):
            raise WorkflowError("handoff outputs must stay in the target project")
        if status == "completed" and (not out_paths or any(not p.exists() for p in out_paths)):
            raise WorkflowError("completed handoff requires existing output files")
        from .storage import file_hash
        event = {"id":uuid.uuid4().hex,"created_at":utc_now(),"role":role,"agent_id":agent_id,"inputs":[str(p) for p in in_paths],"outputs":[str(p) for p in out_paths],"status":status,"summary":summary,"plan_sha256":file_hash(self.root/"plan.json") if (self.root/"plan.json").exists() else None}
        write_json(self.root/"handoffs"/(event["created_at"].replace(":","-")+"-"+event["id"][:8]+".json"),event)
        return self.status()
