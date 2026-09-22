import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import TaskBoard from "../components/TaskBoard";
import MembersPanel from "../components/MembersPanel";
import ProjectMessages from "../components/ProjectMessages";
import { getProject } from "../services/projectService";
import { createTask, updateTaskStatus } from "../services/taskService.js";
import { apiFetch } from "../services/api";
import { useTranslation } from "react-i18next";
import './ProjectDetail.css';

function ProjectDetail()
{
	const { id } = useParams();
	const [project, setProject] = useState(null);
	const [members, setMembers] = useState([]);
	const [tasks, setTasks] = useState([]);
	const [currentUserId, setCurrentUserId] = useState(null);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState("");
	const [title, setTitle] = useState("");
	const [description, setDescription] = useState("");
	const { t } = useTranslation();

	useEffect(() =>
	{ async function fetchProject()
		{
			try {
				const [projectData, meData] = await Promise.all([
					getProject(id),
					apiFetch("/api/users/me"),
				]);
				setProject(projectData.project);
				setMembers(projectData.members);
				setTasks(projectData.tasks);
				setCurrentUserId(meData.user.id);
			}
			catch (err)
			{
				setError(err.message);
			}
			finally
			{
				setLoading(false);
			}
		}
		fetchProject();
	}, [id]);

	async function handleStatusChange(taskId, newStatus)
	{
		setTasks(tasks.map((t) => (t.id === taskId ? { ...t, status: newStatus } : t)));

		try
		{
			await updateTaskStatus(taskId, newStatus);
		}
		catch (err)
		{
			setError(err.message);
		}
	}

	async function handleCreateTask(e)
	{
		e.preventDefault();

		if (!title.trim())
		{
			setError(t("random.titretache"));
			return ;
		}
		try
		{
			const data = await createTask(id, title, description);
			setTasks([...tasks, data.task]);
			setTitle("");
			setDescription("");
			setError("");
		}
		catch (err)
		{
			setError(err.message);
		}
	}

	if (loading)
		return (<p>{t("loading.load")}</p>);
	else if (error && !project)
		return (<p className="error">{t("error.err")} : {error}</p>);

	const isOwner = members.some((m) => m.user_id === currentUserId && m.role === "owner");
	const currentMember = members.find((m) => m.user_id === currentUserId);
	const canManageAttachments = ["owner", "editor"].includes(currentMember?.role);

	return (<div className="project-detail-page">
		<div className="project-detail-header">
			<h1>{project.name}</h1>
			{project.description && <p>{project.description}</p>}
		</div>
		{error && <p className="error">{error}</p>}
		<div className="project-detail-layout">
			<div className="project-detail-main">
				<form onSubmit={handleCreateTask} className="task-form">
					<input type="text" placeholder={t("random.titretache")} value={title} onChange={(e) => setTitle(e.target.value)} />
					<input type="text" placeholder={t("projects.description")} value={description} onChange={(e) => setDescription(e.target.value)} />
					<button type="submit">{t("random.creertache")}</button>
				</form>
				<TaskBoard tasks={tasks} onStatusChange={handleStatusChange} canManageAttachments={canManageAttachments} />
			</div>
			<div className="project-detail-side">
				<MembersPanel
					projectId={id}
					members={members}
					currentUserId={currentUserId}
					onMembersChange={setMembers}
				/>
				<ProjectMessages
					projectId={id}
					currentUserId={currentUserId}
					isOwner={isOwner}
				/>
			</div>
		</div>
	</div>
	);
}

export default ProjectDetail;
