import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import TaskBoard from "../components/TaskBoard";
import MembersPanel from "../components/MembersPanel";
import { createTask, updateTaskStatus } from "../services/taskService.js";
import { getProject } from "../services/projectService.js";
import { getCurrentUser } from "../services/userservice.js";
import { useTranslation } from "react-i18next";
import './ProjectDetail.css';

function ProjectDetail()
{
	const { id } = useParams();
	const [project, setProject] = useState(null);
	const [members, setMembers] = useState([]);
	const [currentUserId, setCurrentUserId] = useState(null);
	const [tasks, setTasks] = useState([]);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState("");
	const [title, setTitle] = useState("");
	const [description, setDescription] = useState("");
	const { t } = useTranslation();

	useEffect(() =>
	{ async function fetchProject()
		{
			try {
				const [data, user] = await Promise.all([getProject(id), getCurrentUser()]);
				setProject(data.project);
				setMembers(data.members);
				setTasks(data.tasks);
				setCurrentUserId(user.user.id);
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

	async function handleCreateTask(e)
	{
		e.preventDefault();
		if (!title.trim())
		{
			setError(t("random.nametask"));
			return ;
		}
		try
		{
			const data = await createTask(id, title.trim(), description.trim() || undefined);
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
	
	if (loading)
		return (<p>{t("loading.load")}</p>);
	else if (error)
		return (<p className="error">{t("error.err")} : {error}</p>);
	return (<div className="project-detail-page">
		<h1>{project.name}</h1>
		{project.description && <p>{project.description}</p>}
		{error && <p className="error">{error}</p>}
		<form onSubmit={handleCreateTask} className="task-form">
			<input type="text" placeholder={t("random.tasknameplaceholder")} value={title} onChange={(e) => setTitle(e.target.value)} />
			<input type="text" placeholder={t("projects.description")} value={description} onChange={(e) => setDescription(e.target.value)} />
			<button type="submit">{t("random.createtask")}</button>
		</form>
		<MembersPanel
			projectId={id}
			members={members}
			currentUserId={currentUserId}
			onMembersChange={setMembers}
		/>
		<TaskBoard tasks={tasks} onStatusChange={handleStatusChange} />
	</div>
	);
}

export default ProjectDetail;