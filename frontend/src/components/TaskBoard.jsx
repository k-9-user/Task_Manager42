import { useTranslation } from "react-i18next";
import TaskCard from "./TaskCard";

function TaskBoard({ tasks, onStatusChange })
{
	const { t } = useTranslation()
	const colonne = [{ key: "todo", label: t("random.afaire")}, { key: "in_progress", label: t("random.encours")}, { key: "done", label: t("random.termine") }];

	return ( <div className="task-board">
		{colonne.map((col) => (<div key={col.key} className="task-colonne">
			<h3>
				{col.label}	
			</h3>
			{tasks
				.filter((task) => task.status === col.key)
				.map((task) => (<TaskCard key={task.id} task={task} onStatusChange={onStatusChange} />
			))}
			</div>	
			))}
	</div>);
}

export default TaskBoard;