import { useTranslation } from "react-i18next";
import { TASK_STATUSES } from "../services/taskService";
import TaskCard from "./TaskCard";
import './TaskBoard.css';

function TaskBoard({ tasks, onStatusChange, onTaskUpdated, onDeleteTask, canEdit, canDelete })
{
	const { t } = useTranslation();

	return (
		<div className="task-board">
			{TASK_STATUSES.map((status) => (
				<div key={status} className="task-column">
					<h3>{t(`tasks.status.${status}`)}</h3>
					{tasks
						.filter((task) => task.status === status)
						.map((task) => (
							<TaskCard key={task.id} task={task} onStatusChange={onStatusChange} onTaskUpdated={onTaskUpdated} onDeleteTask={onDeleteTask} canEdit={canEdit} canDelete={canDelete} />
						))}
				</div>
			))}
		</div>
	);
}

export default TaskBoard;
