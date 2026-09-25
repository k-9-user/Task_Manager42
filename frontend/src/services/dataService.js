import i18n from "../i18n";
import { API_URL, authHeaders, downloadFile, endSession, notifyActivity, translateError } from "./api";

export const MAX_IMPORT_SIZE_MB = 5;

export const IMPORT_TYPES = {
	extensions: [".json", ".csv"],
	mimes: ["application/json", "application/csv", "application/vnd.ms-excel", "text/csv"],
};

export function importAcceptAttr()
{
	return [...IMPORT_TYPES.extensions, ...IMPORT_TYPES.mimes].join(",");
}

export function exportData(format, projectId = null)
{
	const params = new URLSearchParams({ format });

	if (projectId)
		params.append("project_id", projectId);
	return downloadFile(`/api/export?${params.toString()}`, `task-export.${format}`);
}

export function validateImportFile(file)
{
	const name = file.name.toLowerCase();
	const extension = name.includes(".") ? name.slice(name.lastIndexOf(".")) : "";

	if (!IMPORT_TYPES.extensions.includes(extension))
		return "data.errors.type";
	if (file.size > MAX_IMPORT_SIZE_MB * 1024 * 1024)
		return "data.errors.size";
	return null;
}

export async function importData(file)
{
	const formData = new FormData();
	formData.append("file", file);

	let response;
	try
	{
		response = await fetch(`${API_URL}/api/import`,
			{ method: "POST", headers: authHeaders(), body: formData });
	}
	catch
	{
		throw new Error(i18n.t("error.network"));
	}
	if (response.status === 401)
	{
		endSession();
		throw new Error(i18n.t("error.sessionExpired"));
	}
	if (response.status === 413)
		throw new Error(i18n.t("data.errors.size", { max: MAX_IMPORT_SIZE_MB }));

	const isJson = response.headers.get("Content-Type")?.includes("application/json");
	const result = isJson ? await response.json() : null;

	if (!result?.success)
		throw new Error(translateError(result?.error));
	notifyActivity();
	return result.data;
}
