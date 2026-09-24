import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { MAX_UPLOAD_SIZE_MB, acceptAttr, typesLabel, validateFile } from "../services/upload";

function FileUpload({ types, upload, onUploaded, pickLabel, sendLabel })
{
	const [file, setFile] = useState(null);
	const [uploading, setUploading] = useState(false);
	const [progress, setProgress] = useState(0);
	const [error, setError] = useState("");
	const fileInputRef = useRef(null);
	const { t } = useTranslation();

	function resetInput()
	{
		setFile(null);
		if (fileInputRef.current)
			fileInputRef.current.value = "";
	}

	function handleFileChange(e)
	{
		const selected = e.target.files?.[0] ?? null;
		const invalid = selected && validateFile(selected, types);

		if (invalid)
		{
			resetInput();
			setError(t(invalid, { max: MAX_UPLOAD_SIZE_MB }));
			return ;
		}
		setFile(selected);
		setError("");
	}

	async function handleUpload()
	{
		setProgress(0);
		setUploading(true);
		setError("");

		try
		{
			await upload(file, setProgress);
			await onUploaded();
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
		<div className="upload-block">
			<input ref={fileInputRef} type="file" accept={acceptAttr(types)} onChange={handleFileChange} hidden />
			<button type="button" onClick={() => fileInputRef.current?.click()} disabled={uploading}>
				{pickLabel}
			</button>
			{file && <span>{file.name}</span>}
			{file && (
				<button type="button" onClick={handleUpload} disabled={uploading}>
					{uploading ? t("loading.sending") : sendLabel}
				</button>
			)}
			{uploading && (
				<div className="upload-progress">
					<progress value={progress} max="100" aria-label={t("attachments.progress")} />
					<span>{progress}%</span>
				</div>
			)}
			<div className="upload-hint">
				<small>{t("attachments.hintTypes", { types: typesLabel(types) })}</small>
				<small>{t("attachments.hintSize", { max: MAX_UPLOAD_SIZE_MB })}</small>
			</div>
			{error && <p className="error">{error}</p>}
		</div>
	);
}

export default FileUpload;
