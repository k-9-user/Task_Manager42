import { useRef, useState } from "react";
import { uploadAttachement } from "../services/taskService";
import { useTranslation } from "react-i18next";

function AttachmentUpload({ taskId, uploadsuccess})
{
	const [file, setfile] = useState(null);
	const [uploading, setUploading] = useState(false);
	const [error, setError] = useState("");
	const fileInputRef = useRef(null);
	const { t } = useTranslation();

	function handleFileChange(e)
	{
		setfile(e.target.files?.[0] ?? null);
		setError("");
	}

	async function handleUpload()
	{
		if (!file)
		{
			setError(t("random.sfichier"));
			return ;
		}

		setUploading(true);
		setError("");

		try
		{
			const attachment = await uploadAttachement(taskId, file);
			await uploadsuccess(attachment);
			setfile(null);
			if (fileInputRef.current)
				fileInputRef.current.value = "";
		}
		catch (err)
		{
			setError(err.message);
		}
		finally
		{
			setUploading(false);
		}
	}
	return (
		<div className="attachement-upload">
			<input ref={fileInputRef} type="file" onChange={handleFileChange} hidden />
			<button type="button" onClick={() => fileInputRef.current?.click()} disabled={uploading}>
				{t("random.addfichier")}
			</button>
			{file && <span>{file.name}</span>}
			{file && (
				<button type="button" onClick={handleUpload} disabled={uploading}>
					{uploading ? t("random.envoi") : t("random.ajfichier")}
				</button>
			)}
			{error && <p className="error">{error}</p>}
		</div>
	);
}

export default AttachmentUpload;
