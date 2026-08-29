import { useState } from "react";
import { uploadAttachement } from "../services/taskService";

function AttachmentUpload({ taskId, uploadsuccess})
{
	const [file, setfile] = useState(null);
	const [uploading, setUploading] = useState(false);
	const [error, setError] = useState("");

	function handleFileChange(e)
	{
		setfile(e.target.files[0]);
		setError("");
	}

	async function handleUpload()
	{
		if (!file)
		{
			setError("Sélectionner un fichier");
			return ;
		}

		setUploading(true);
		setError("");

		try
		{
			const attachment = await uploadAttachement(taskId, file);
			uploadsuccess(attachment);
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
			<input type="file" onChange={handleFileChange} />
			<button onClick={handleUpload} disabled={uploading}>
				{uploading ? "Envoi..." : "Ajouter le fichier"}
			</button>
			{error && <p className="error">{error}</p>}
		</div>
	);
}

export default AttachmentUpload;