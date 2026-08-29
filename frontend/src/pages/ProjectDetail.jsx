import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import TaskBoard from "../components/TaskBoard";
import { getProjectTasks, updateTaskStatus } from "../services/taskService.js";
import { useTranslation } from "react-i18next";

const USE_MOCK = true;


const mockTasks = [{ id: "1", title: "Créer la maquette", status: "todo" }, { id: "2", title: "Setup Vite", status: "done" }, { id: "3", title: "Page login", status: "in_progress" },];

function ProjectDetail()
{
	const { id } = useParams();
	const [tasks, setTasks] = useState([]);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState("");
	const { t } = useTranslation();

	useEffect(() =>
	{ async function fetchTasks()
		{
			try {
				if (USE_MOCK)
			    	setTasks(mockTasks);
				else
				{
					const data = await getProjectTasks(id);
					setTasks(data.tasks);
				}
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
		fetchTasks();
	}, [id]);

	async function handleStatusChange(taskId, newStatus)
	{
		setTasks(tasks.map((t) => (t.id === taskId ? { ...t, status: newStatus } : t)));

		if (!USE_MOCK)
		{
			try
			{
				await updateTaskStatus(taskId, newStatus);
			}
			catch (err)
			{
				setError(err.message);
			}
		}
	}
	
	if (loading)
		return (<p>{t("loading.load")}</p>);
	else if (error)
		return (<p className="error">{t("error.err")} : {error}</p>);
	return (<div className="project-detail-page">
		<h1>{t("random.projet")} #{id}</h1>
		<TaskBoard tasks={tasks} onStatusChange={handleStatusChange} />
	</div>
	);
}

export default ProjectDetail;