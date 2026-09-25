import i18n from "../i18n";
import { API_URL, authHeaders, endSession, notifyActivity, translateError } from "./api";

export const MAX_UPLOAD_SIZE_MB = Number(import.meta.env.VITE_MAX_UPLOAD_SIZE_MB) || 10;
const MAX_UPLOAD_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024;

export const ATTACHMENT_TYPES = {
	mimes: ["application/pdf", "image/jpeg", "image/png", "text/csv", "text/plain"],
	extensions: [".pdf", ".jpg", ".jpeg", ".png", ".csv", ".txt"],
};

export const BANNER_TYPES = {
	mimes: ["image/jpeg", "image/png"],
	extensions: [".jpg", ".jpeg", ".png"],
};

export function acceptAttr(types)
{
	return [...types.extensions, ...types.mimes].join(",");
}

export function typesLabel(types)
{
	return [...new Set(types.extensions.map((ext) => ext.slice(1).replace("jpeg", "jpg")))].join(", ");
}

export function validateFile(file, types)
{
	const name = file.name.toLowerCase();
	const extension = name.includes(".") ? name.slice(name.lastIndexOf(".")) : "";

	if (!types.extensions.includes(extension) || !types.mimes.includes(file.type))
		return "attachments.errors.type";
	if (file.size > MAX_UPLOAD_BYTES)
		return "attachments.errors.size";
	return null;
}

export function uploadWithProgress(endpoint, file, onProgress)
{
	return new Promise((resolve, reject) =>
	{
		const xhr = new XMLHttpRequest();
		const formData = new FormData();

		formData.append("file", file);
		xhr.open("POST", `${API_URL}${endpoint}`);
		for (const [name, value] of Object.entries(authHeaders()))
			xhr.setRequestHeader(name, value);

		xhr.upload.onprogress = (e) =>
		{
			if (e.lengthComputable && onProgress)
				onProgress(Math.round((e.loaded / e.total) * 100));
		};

		xhr.onload = () =>
		{
			let result = null;
			try
			{
				result = JSON.parse(xhr.responseText);
			}
			catch
			{
				result = null;
			}
			if (result?.success)
			{
				notifyActivity();
				return resolve(result.data);
			}
			if (xhr.status === 401)
			{
				endSession();
				return reject(new Error(i18n.t("error.sessionExpired")));
			}
			if (xhr.status === 413)
				return reject(new Error(i18n.t("attachments.errors.size", { max: MAX_UPLOAD_SIZE_MB })));
			reject(new Error(result?.error ? translateError(result.error) : i18n.t("attachments.errors.upload")));
		};
		xhr.onerror = () => reject(new Error(i18n.t("attachments.errors.upload")));
		xhr.onabort = () => reject(new Error(i18n.t("attachments.errors.upload")));

		xhr.send(formData);
	});
}
