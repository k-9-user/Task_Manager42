import { useRef, useState } from "react";
import { uploadAttachement } from "../services/taskService";
import { useTranslation } from "react-i18next";
import { ATTACHMENT_TYPES, MAX_UPLOAD_SIZE_MB, acceptAttr, typesLabel, validateFile } from "../services/upload";

function AttachmentUpload({ taskId, uploadsuccess})
{
	const [file, setfile] = useState(null);
	const [uploading, setUploading] = useState(false);
	const [progress, setProgress] = useState(0);
	const [error, setError] = useState("");
	const fileInputRef = useRef(null);
	const { t } = useTranslation();

	function resetInput()
	{
		setfile(null);
		if (fileInputRef.current)
			fileInputRef.current.value = "";
	}

	function handleFileChange(e)
	{
		const selected = e.target.files?.[0] ?? null;
		const invalid = selected && validateFile(selected, ATTACHMENT_TYPES);

		if (invalid)
		{
			resetInput();
			setError(t(invalid, { max: MAX_UPLOAD_SIZE_MB }));
			return ;
		}
		setfile(selected);
		setError("");
	}

	async function handleUpload()
	{
		if (!file)
		{
			setError(t("random.sfichier"));
			return ;
		}
		const invalid = validateFile(file, ATTACHMENT_TYPES);
		if (invalid)
		{
			setError(t(invalid, { max: MAX_UPLOAD_SIZE_MB }));
			return ;
		}

		setProgress(0);
		setUploading(true);
		setError("");

		try
		{
			const attachment = await uploadAttachement(taskId, file, setProgress);
			await uploadsuccess(attachment);
			resetInput();
		}
		catch (err)
		{
			setError(err.message);
		}
		finally
		{
			setUploading(false);
			setProgress(0);
		}
	}
	return (
		<div className="attachement-upload">
			<input ref={fileInputRef} type="file" accept={acceptAttr(ATTACHMENT_TYPES)} onChange={handleFileChange} hidden />
			<button type="button" onClick={() => fileInputRef.current?.click()} disabled={uploading}>
				{t("random.addfichier")}
			</button>
			{file && <span>{file.name}</span>}
			{file && (
				<button type="button" onClick={handleUpload} disabled={uploading}>
					{uploading ? t("random.envoi") : t("random.ajfichier")}
				</button>
			)}
			{uploading && (
				<div className="upload-progress">
					<progress value={progress} max="100" aria-label={t("attachments.progress")} />
					<span>{progress}%</span>
				</div>
			)}
			<small className="upload-hint">
				{t("attachments.hint", { types: typesLabel(ATTACHMENT_TYPES), max: MAX_UPLOAD_SIZE_MB })}
			</small>
			{error && <p className="error">{error}</p>}
		</div>
	);
}

export default AttachmentUpload;
