import { useEffect, useRef, useState } from "react";
import AttachmentUpload from "./AttachmentUpload";
import BannerUpload from "./BannerUpload";
import CommentSection from "./CommentSection";
import { deleteAttachment, getTaskAttachments } from "../services/taskService";
import { fetchAuthenticatedBlobUrl } from "../services/api";
import { useTranslation } from "react-i18next";
import './TaskCard.css';

function TaskCard ({ task, onStatusChange, canManageAttachments })
{
	const [attachments, setAttachments] = useState([]);
	const [attachmentError, setAttachmentError] = useState("");
	const attachmentLoadId = useRef(0);
	const [hasBanner, setHasBanner] = useState(!!task.banner_url);
	const [bannerBlobUrl, setBannerBlobUrl] = useState(null);
	const [bannerVersion, setBannerVersion] = useState(0);
	const [showcomments, setshowcomments] = useState(false);
	const { t } = useTranslation();

	useEffect(() =>
	{
		const loadId = ++attachmentLoadId.current;
		getTaskAttachments(task.id)
			.then((data) => {
				if (loadId === attachmentLoadId.current)
					setAttachments(data.attachments);
			})
			.catch((err) => {
				if (loadId === attachmentLoadId.current)
					setAttachmentError(err.message);
			});
		return () => { attachmentLoadId.current++; };
	}, [task.id]);

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
	}, [hasBanner, bannerVersion, task.id]);

	async function uploadsuccess()
	{
		const loadId = ++attachmentLoadId.current;
		const data = await getTaskAttachments(task.id);
		if (loadId === attachmentLoadId.current)
		{
			setAttachments(data.attachments);
			setAttachmentError("");
		}
	}

	async function handlePreview(attachment)
	{
		const win = window.open("", "_blank");
		try
		{
			const url = await fetchAuthenticatedBlobUrl(`/api/attachments/${attachment.id}`);
			if (win)
			{
				win.opener = null;
				win.location.href = url;
			}
			setTimeout(() => URL.revokeObjectURL(url), 60000);
			setAttachmentError("");
		}
		catch (err)
		{
			win?.close();
			setAttachmentError(err.message);
		}
	}

	async function handleDownload(attachment)
	{
		try
		{
			const url = await fetchAuthenticatedBlobUrl(`/api/attachments/${attachment.id}`);
			const link = document.createElement("a");
			link.href = url;
			link.download = attachment.filename;
			document.body.appendChild(link);
			link.click();
			link.remove();
			setTimeout(() => URL.revokeObjectURL(url), 1000);
			setAttachmentError("");
		}
		catch (err)
		{
			setAttachmentError(err.message);
		}
	}

	async function handleDelete(attachment)
	{
		try
		{
			await deleteAttachment(attachment.id);
			setAttachments((current) => current.filter((item) => item.id !== attachment.id));
			setAttachmentError("");
		}
		catch (err)
		{
			setAttachmentError(err.message);
		}
	}

	function bannerUploadSuccess()
	{
		setHasBanner(true);
		setBannerVersion((version) => version + 1);
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
			{attachmentError && <p className="error" role="alert">{attachmentError}</p>}
			{attachments.length > 0 && (
				<ul className="task-atachments">
					{
						attachments.map((att) =>
							(	
								<li key={att.id}>
									<span>📎{att.filename}</span>
									<div className="attachment-actions">
										<button type="button" onClick={() => handlePreview(att)}>{t("attachments.preview")}</button>
										<button type="button" onClick={() => handleDownload(att)}>{t("attachments.download")}</button>
										{canManageAttachments && <button type="button" onClick={() => handleDelete(att)}>{t("attachments.delete")}</button>}
									</div>
								</li>
							)
						)
					}
				</ul>
			)}
			{canManageAttachments && <AttachmentUpload taskId={task.id} uploadsuccess={uploadsuccess} />}
			{canManageAttachments && <BannerUpload taskId={task.id} uploadsuccess={bannerUploadSuccess} />}
			<button onClick={() => setshowcomments(!showcomments)}>
				{showcomments ? t("random.masquercommentaires") : t("random.voircommentaires")}
			</button>
			{showcomments && <CommentSection taskId={task.id} />}
		</div>
	);
}

export default TaskCard;
