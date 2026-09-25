import { useEffect, useRef, useState } from "react";
import CommentSection from "./CommentSection";
import FileUpload from "./FileUpload";
import { TASK_STATUSES, deleteAttachment, getTaskAttachments, updateTaskDescription, uploadAttachment, uploadTaskBanner } from "../services/taskService";
import { downloadFile, fetchAuthenticatedBlobUrl } from "../services/api";
import { ATTACHMENT_TYPES, BANNER_TYPES } from "../services/upload";
import { useTranslation } from "react-i18next";
import './TaskCard.css';

function TaskCard ({ task, currentUserId, onStatusChange, onTaskUpdated, onDeleteTask, canEdit, canDelete })
{
	const [attachments, setAttachments] = useState([]);
	const [attachmentError, setAttachmentError] = useState("");
	const attachmentLoadId = useRef(0);
	const [hasBanner, setHasBanner] = useState(!!task.banner_url);
	const [bannerBlobUrl, setBannerBlobUrl] = useState(null);
	const [bannerVersion, setBannerVersion] = useState(0);
	const [showComments, setShowComments] = useState(false);
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

	async function refreshAttachments()
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
			await downloadFile(`/api/attachments/${attachment.id}`, attachment.filename);
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
				<button type="button" className="task-description-edit" onClick={startEditDescription}>{t("tasks.editDescription")}</button>
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
			<select value={task.status} disabled={!canEdit} aria-label={t("tasks.statusLabel")} onChange={(e) => onStatusChange(task.id, e.target.value)}>
				{TASK_STATUSES.map((status) => (
					<option key={status} value={status}>{t(`tasks.status.${status}`)}</option>
				))}
			</select>
			{attachmentError && <p className="error" role="alert">{attachmentError}</p>}
			{attachments.length > 0 && (
				<ul className="task-attachments">
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
			{canEdit && (
				<FileUpload
					types={ATTACHMENT_TYPES}
					upload={(file, onProgress) => uploadAttachment(task.id, file, onProgress)}
					onUploaded={refreshAttachments}
					pickLabel={t("attachments.pick")}
					sendLabel={t("attachments.upload")}
				/>
			)}
			{canEdit && (
				<FileUpload
					types={BANNER_TYPES}
					upload={(file, onProgress) => uploadTaskBanner(task.id, file, onProgress)}
					onUploaded={bannerUploadSuccess}
					pickLabel={t("attachments.pickBanner")}
					sendLabel={t("attachments.uploadBanner")}
				/>
			)}
			<button onClick={() => setShowComments(!showComments)}>
				{showComments ? t("comments.hide") : t("comments.show")}
			</button>
			{showComments && <CommentSection taskId={task.id} currentUserId={currentUserId} isOwner={canDelete} />}
			{canDelete && (
				<button type="button" className="task-delete" onClick={() => onDeleteTask(task)}>{t("tasks.delete")}</button>
			)}
		</div>
	);
}

export default TaskCard;
