import { useState } from "react";
import { uploadTaskBanner } from "../services/taskService";
import { useTranslation } from "react-i18next";

function BannerUpload({ taskId, uploadsuccess })
{
	const [file, setfile] = useState(null);
	const [uploading, setUploading] = useState(false);
	const [error, setError] = useState("");
	const { t } = useTranslation();

	function handleFileChange(e)
	{
		setfile(e.target.files[0]);
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
			const data = await uploadTaskBanner(taskId, file);
			uploadsuccess(data.banner_url);
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
		<div className="banner-upload">
			<input type="file" accept="image/png,image/jpeg" onChange={handleFileChange} />
			<button onClick={handleUpload} disabled={uploading}>
				{uploading ? t("random.envoi") : t("random.ajbanniere")}
			</button>
			{error && <p className="error">{error}</p>}
		</div>
	);
}

export default BannerUpload;
