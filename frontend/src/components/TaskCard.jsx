function TaskCard ({ task, onStatusChange })
{
	return (
		<div className="task-card">
			<h4>
				{task.title}
			</h4>
			{task.description && <p>{task.description}</p>}
			<select value={task.status} onChange={(e) => onStatusChange(task.id, e.target.value)}>
				<option value="todo">A faire</option>
				<option value="in_progress">En cours</option>
				<option value="done">Termine</option>
			</select>
		</div>
	);
}

export default TaskCard;