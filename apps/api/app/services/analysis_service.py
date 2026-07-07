"""AI解析(パーツ設計・質問・セグメンテーションタスク生成)。"""
from __future__ import annotations

from app.ai.mock_analyzer import get_analyzer
from app.core.paths import ProjectPaths
from app.models.parts import PartsPlan
from app.models.segmentation import QuestionList, SegmentationTaskList
from app.services.project_service import load_project, save_parts, save_project


def analyze(project_id: str, analyzer_name: str = "mock") -> PartsPlan:
    project = load_project(project_id)
    paths = ProjectPaths(project_id)
    analyzer = get_analyzer(analyzer_name)
    plan = analyzer.analyze_character_image(
        paths.normalized_image, project.preferences
    )
    save_parts(project_id, plan)
    project = load_project(project_id)
    project.status.analysis_done = True
    save_project(project)
    return plan


def generate_questions(project_id: str, analyzer_name: str = "mock") -> QuestionList:
    project = load_project(project_id)
    analyzer = get_analyzer(analyzer_name)
    return analyzer.generate_questions(project.preferences)


def generate_segmentation_tasks(
    project_id: str, plan: PartsPlan, analyzer_name: str = "mock"
) -> SegmentationTaskList:
    analyzer = get_analyzer(analyzer_name)
    task_list = analyzer.generate_segmentation_tasks(plan)
    paths = ProjectPaths(project_id)
    paths.segmentation_tasks_json.write_text(
        task_list.model_dump_json(indent=2), encoding="utf-8"
    )
    return task_list
