import { useState } from "react";
import AttachmentUpload from "./AttachmentUpload";
import { useTranslation } from "react-i18next";

function TaskCard ({ task, onStatusChange })
{
	const [attachements, setAttachements] = useState(task.attachements || []);
	const [showupload, setshowupload] = useState(false);
	const { t } = useTranslation();

	function uploadsuccess(newattachement)
	{
		setAttachements([...attachements, newattachement]);
		setshowupload(false);
	}
	return (
		<div className="task-card">
			<h4>
				{task.title}
			</h4>
			{task.description && <p>{task.description}</p>}
			<select value={task.status} onChange={(e) => onStatusChange(task.id, e.target.value)}>
				<option value="todo">{t("random.afaire")}</option>
				<option value="in_progress">{t("random.encours")}</option>
				<option value="done">{t("random.termine")}</option>
			</select>
			{attachements.length > 0 && (
				<ul className="task-atachments">
					{
						attachements.map((att) =>
							(	
								<li key={att.id}>📎{att.file_name}</li>
							)
						)
					}
				</ul>
			)}
			{showupload ? (
				<AttachmentUpload taskId={task.id} uploadsuccess={uploadsuccess} />
			) : (<button onClick={() => setshowupload(true)}>{t("random.addfichier")}</button>)
			}
		</div>
	);
}

export default TaskCard;