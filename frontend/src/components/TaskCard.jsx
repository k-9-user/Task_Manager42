import { useState } from "react";
import AttachmentUpload from "./AttachmentUpload";
import BannerUpload from "./BannerUpload";
import CommentSection from "./CommentSection";
import { useTranslation } from "react-i18next";
import './TaskCard.css';

function TaskCard ({ task, onStatusChange })
{
	const [attachements, setAttachements] = useState(task.attachements || []);
	const [showupload, setshowupload] = useState(false);
	const [bannerUrl, setBannerUrl] = useState(task.banner_url || null);
	const [showBannerUpload, setShowBannerUpload] = useState(false);
	const [showComments, setShowComments] = useState(false);
	const { t } = useTranslation();
	const API_URL = import.meta.env.VITE_API_URL;

	function uploadsuccess(newattachement)
	{
		setAttachements([...attachements, newattachement]);
		setshowupload(false);
	}

	function bannerUploadSuccess(newBannerUrl)
	{
		setBannerUrl(newBannerUrl);
		setShowBannerUpload(false);
	}

	return (
		<div className="task-card">
			{bannerUrl && (
				<img className="task-banner" src={`${API_URL}${bannerUrl}`} alt="" />
			)}
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
			{showBannerUpload ? (
				<BannerUpload taskId={task.id} uploadsuccess={bannerUploadSuccess} />
			) : (<button onClick={() => setShowBannerUpload(true)}>{t("random.addbanniere")}</button>)
			}
			{showComments ? (
				<CommentSection taskId={task.id} />
			) : (<button onClick={() => setShowComments(true)}>{t("random.voircommentaires")}</button>)
			}
		</div>
	);
}

export default TaskCard;