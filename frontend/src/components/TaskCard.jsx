import { useEffect, useState } from "react";
import AttachmentUpload from "./AttachmentUpload";
import BannerUpload from "./BannerUpload";
import CommentSection from "./CommentSection";
import { fetchAuthenticatedBlobUrl } from "../services/api";
import { useTranslation } from "react-i18next";
import './TaskCard.css';

function TaskCard ({ task, onStatusChange })
{
	const [attachements, setAttachements] = useState(task.attachements || []);
	const [showupload, setshowupload] = useState(false);
	const [hasBanner, setHasBanner] = useState(!!task.banner_url);
	const [bannerBlobUrl, setBannerBlobUrl] = useState(null);
	const [showbanner, setshowbanner] = useState(false);
	const [showcomments, setshowcomments] = useState(false);
	const { t } = useTranslation();

	useEffect(() =>
	{
		if (!hasBanner)
		{
			setBannerBlobUrl(null);
			return ;
		}
		let objectUrl = null;
		let cancelled = false;
		fetchAuthenticatedBlobUrl(`/api/tasks/${task.id}/banner/file`)
			.then((url) => {
				if (cancelled)
				{
					URL.revokeObjectURL(url);
					return ;
				}
				objectUrl = url;
				setBannerBlobUrl(url);
			})
			.catch(() => {});
		return () => {
			cancelled = true;
			if (objectUrl)
				URL.revokeObjectURL(objectUrl);
		};
	}, [hasBanner, task.id]);

	function uploadsuccess(newattachement)
	{
		setAttachements([...attachements, newattachement]);
		setshowupload(false);
	}

	function bannerUploadSuccess()
	{
		setHasBanner(true);
		setshowbanner(false);
	}
	return (
		<div className="task-card">
			{bannerBlobUrl && <img className="task-banner" src={bannerBlobUrl} alt={task.title} />}
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
			{showbanner ? (
				<BannerUpload taskId={task.id} uploadsuccess={bannerUploadSuccess} />
			) : (<button onClick={() => setshowbanner(true)}>{t("random.addbanniere")}</button>)
			}
			<button onClick={() => setshowcomments(!showcomments)}>
				{showcomments ? t("random.masquercommentaires") : t("random.voircommentaires")}
			</button>
			{showcomments && <CommentSection taskId={task.id} />}
		</div>
	);
}

export default TaskCard;