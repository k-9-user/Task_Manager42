import { useRef, useState } from "react";
import { uploadTaskBanner } from "../services/taskService";
import { useTranslation } from "react-i18next";
import { BANNER_TYPES, MAX_UPLOAD_SIZE_MB, acceptAttr, typesLabel, validateFile } from "../services/upload";

function BannerUpload({ taskId, uploadsuccess })
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
		const invalid = selected && validateFile(selected, BANNER_TYPES);

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
		const invalid = validateFile(file, BANNER_TYPES);
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
			const data = await uploadTaskBanner(taskId, file, setProgress);
			uploadsuccess(data.banner_url);
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
		<div className="banner-upload">
			<input ref={fileInputRef} type="file" accept={acceptAttr(BANNER_TYPES)} onChange={handleFileChange} hidden />
			<button type="button" onClick={() => fileInputRef.current?.click()} disabled={uploading}>
				{t("random.addbanniere")}
			</button>
			{file && <span>{file.name}</span>}
			{file && (
				<button type="button" onClick={handleUpload} disabled={uploading}>
					{uploading ? t("random.envoi") : t("random.ajbanniere")}
				</button>
			)}
			{uploading && (
				<div className="upload-progress">
					<progress value={progress} max="100" aria-label={t("attachments.progress")} />
					<span>{progress}%</span>
				</div>
			)}
			<small className="upload-hint">
				{t("attachments.hint", { types: typesLabel(BANNER_TYPES), max: MAX_UPLOAD_SIZE_MB })}
			</small>
			{error && <p className="error">{error}</p>}
		</div>
	);
}

export default BannerUpload;
