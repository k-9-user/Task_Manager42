import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import TaskBoard from "../components/TaskBoard";
import MembersPanel from "../components/MembersPanel";
import ProjectMessages from "../components/ProjectMessages";
import { getProject } from "../services/projectService";
import { createTask, deleteTask, updateTaskStatus } from "../services/taskService.js";
import { getMe } from "../services/userservice";
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
					getMe(),
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
		setTasks(tasks.map((task) => (task.id === taskId ? { ...task, status: newStatus } : task)));

		try
		{
			await updateTaskStatus(taskId, newStatus);
		}
		catch (err)
		{
			setError(err.message);
		}
	}

	function handleTaskUpdated(updatedTask)
	{
		setTasks((current) => current.map((task) => (task.id === updatedTask.id
			? { ...task, description: updatedTask.description, updated_at: updatedTask.updated_at }
			: task)));
	}

	async function handleDeleteTask(task)
	{
		if (!window.confirm(t("tasks.confirmDelete", { title: task.title })))
			return ;
		try
		{
			await deleteTask(task.id);
			setTasks((current) => current.filter((item) => item.id !== task.id));
			setError("");
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
			setError(t("tasks.titleRequired"));
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

	const currentMember = members.find((m) => m.user_id === currentUserId);
	const isOwner = currentMember?.role === "owner";
	const canEdit = ["owner", "editor"].includes(currentMember?.role);

	return (<div className="project-detail-page">
		<div className="project-detail-header">
			<h1>{project.name}</h1>
			{project.description && <p>{project.description}</p>}
		</div>
		{error && <p className="error">{error}</p>}
		<div className="project-detail-layout">
			<div className="project-detail-main">
				<form onSubmit={handleCreateTask} className="task-form">
					<input type="text" placeholder={t("tasks.titlePlaceholder")} value={title} onChange={(e) => setTitle(e.target.value)} />
					<input type="text" placeholder={t("projects.description")} value={description} onChange={(e) => setDescription(e.target.value)} />
					<button type="submit">{t("tasks.create")}</button>
				</form>
				<TaskBoard tasks={tasks} onStatusChange={handleStatusChange} onTaskUpdated={handleTaskUpdated} onDeleteTask={handleDeleteTask} canEdit={canEdit} canDelete={isOwner} />
			</div>
			<div className="project-detail-side">
				<MembersPanel
					projectId={id}
					members={members}
					currentUserId={currentUserId}
					isOwner={isOwner}
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
