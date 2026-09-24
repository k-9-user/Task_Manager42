import { useEffect, useRef, useState } from "react";
import AttachmentUpload from "./AttachmentUpload";
import BannerUpload from "./BannerUpload";
import CommentSection from "./CommentSection";
import { deleteAttachment, getTaskAttachments, updateTaskDescription } from "../services/taskService";
import { fetchAuthenticatedBlobUrl } from "../services/api";
import { useTranslation } from "react-i18next";
import './TaskCard.css';

function TaskCard ({ task, onStatusChange, onTaskUpdated, canEdit })
{
	const [attachments, setAttachments] = useState([]);
	const [attachmentError, setAttachmentError] = useState("");
	const attachmentLoadId = useRef(0);
	const [hasBanner, setHasBanner] = useState(!!task.banner_url);
	const [bannerBlobUrl, setBannerBlobUrl] = useState(null);
	const [bannerVersion, setBannerVersion] = useState(0);
	const [showcomments, setshowcomments] = useState(false);
	const [editingDescription, setEditingDescription] = useState(false);
	const [descriptionDraft, setDescriptionDraft] = useState("");
	const [savingDescription, setSavingDescription] = useState(false);
	const [descriptionError, setDescriptionError] = useState("");
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

	function startEditDescription()
	{
		setDescriptionDraft(task.description ?? "");
		setDescriptionError("");
		setEditingDescription(true);
	}

	async function handleSaveDescription(e)
	{
		e.preventDefault();
		setSavingDescription(true);
		setDescriptionError("");
		try
		{
			const data = await updateTaskDescription(task.id, descriptionDraft.trim() || null);
			onTaskUpdated(data.task);
			setEditingDescription(false);
		}
		catch (err)
		{
			setDescriptionError(err.message);
		}
		finally
		{
			setSavingDescription(false);
		}
	}

	return (
		<div className="task-card">
			{bannerBlobUrl && <img className="task-banner" src={bannerBlobUrl} alt={task.title} />}
			<h4>
				{task.title}
			</h4>
			{!editingDescription && task.description && <p className="task-description">{task.description}</p>}
			{canEdit && !editingDescription && (
				<button type="button" onClick={startEditDescription}>{t("tasks.editDescription")}</button>
			)}
			{editingDescription && (
				<form className="task-description-form" onSubmit={handleSaveDescription}>
					<textarea
						aria-label={t("tasks.descriptionLabel")}
						value={descriptionDraft}
						onChange={(e) => setDescriptionDraft(e.target.value)}
						maxLength={5000}
						rows={4}
						autoFocus
					/>
					<div className="task-description-actions">
						<button type="button" onClick={() => setEditingDescription(false)} disabled={savingDescription}>
							{t("tasks.cancel")}
						</button>
						<button type="submit" disabled={savingDescription}>
							{savingDescription ? t("tasks.saving") : t("tasks.save")}
						</button>
					</div>
					{descriptionError && <p className="error" role="alert">{descriptionError}</p>}
				</form>
			)}
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
										{canEdit && <button type="button" onClick={() => handleDelete(att)}>{t("attachments.delete")}</button>}
									</div>
								</li>
							)
						)
					}
				</ul>
			)}
			{canEdit && <AttachmentUpload taskId={task.id} uploadsuccess={uploadsuccess} />}
			{canEdit && <BannerUpload taskId={task.id} uploadsuccess={bannerUploadSuccess} />}
			<button onClick={() => setshowcomments(!showcomments)}>
				{showcomments ? t("random.masquercommentaires") : t("random.voircommentaires")}
			</button>
			{showcomments && <CommentSection taskId={task.id} />}
		</div>
	);
}

export default TaskCard;
