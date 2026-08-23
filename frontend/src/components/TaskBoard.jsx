import TaskCard from "./TaskCard";

function TaskBoard({ tasks, onStatusChange })
{
	const colonne = [{ key: "todo", label: "A faire"}, { key: "in_progress", label: "En cours"}, { key: "done", label: "Termine" }];

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