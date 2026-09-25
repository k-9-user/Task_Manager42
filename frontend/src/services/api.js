import i18n from "../i18n";

export const API_URL = import.meta.env.VITE_API_URL;

export const TOKEN_KEY = "taskmanager.token";

export const ACTIVITY_EVENT = "taskmanager:activity";

const ERROR_KEYS = {
	"Invalid email, username or password": "error.invalidCredentials",
	"Account is banned": "error.banned",
	"Too many requests": "error.tooManyRequests",
	"Rate limit exceeded": "error.tooManyRequests",
	"Invalid request": "error.invalidRequest",
	"Username already taken": "error.usernameTaken",
	"Email already registered": "error.accountExists",
	"An account with this email already exists": "error.accountExists",
	"Email or username already exists": "error.accountExists",
	"User not found": "error.userNotFound",
	"User not found or already a project member": "error.memberUnavailable",
	"Cannot remove the last project owner": "error.lastOwner",
	"At least one administrator is required": "error.lastAdmin",
	"At least one active administrator is required": "error.lastAdmin",
	"The bootstrap administrator is protected": "error.bootstrapAdmin",
	"Project not found": "error.notFound",
	"Task not found": "error.notFound",
	"Comment not found": "error.notFound",
	"Message not found": "error.notFound",
	"Attachment not found": "error.notFound",
	"Attachment file not found": "error.notFound",
	"Banner not found": "error.notFound",
	"Member not found": "error.notFound",
	"Permission denied": "error.forbidden",
	"Project membership is read-only": "error.forbidden",
	"Admin access required": "error.forbidden",
	"Only the project owner can delete tasks": "error.forbidden",
	"Only the comment author or the project owner may delete this comment": "error.forbidden",
	"Only the message author or the project owner may delete this message": "error.forbidden",
	"Unsupported attachment type": "attachments.errors.type",
	"Unsupported banner image type": "attachments.errors.type",
	"Invalid attachment filename": "attachments.errors.type",
	"Attachment exceeds the configured size limit": "error.fileTooLarge",
	"Export format must be json or csv": "data.errors.type",
	"Import file must be a JSON or CSV file": "data.errors.type",
	"Import file is empty": "data.errors.empty",
	"Import contains no tasks": "data.errors.empty",
	"Import file must be valid UTF-8": "data.errors.encoding",
	"Import contains too many tasks": "data.errors.tooMany",
	"CSV import requires project_id and title columns": "data.errors.columns",
	"Task assignee must be a project member": "data.errors.assignee",
	"Malformed JSON import": "data.errors.invalid",
	"JSON import must be an object": "data.errors.invalid",
	"JSON tasks must be a list of objects": "data.errors.invalid",
	"JSON import must contain projects or tasks": "data.errors.invalid",
	"JSON tasks must be objects": "data.errors.invalid",
	"Each imported project must contain an id": "data.errors.invalid",
	"Each imported project must contain a tasks list": "data.errors.invalid",
	"Task project_id does not match its project": "data.errors.invalid",
	"Malformed CSV import": "data.errors.invalid",
	"Malformed CSV row": "data.errors.invalid",
	"Invalid task import data": "data.errors.invalid",
};

export function translateError(message) {
	return i18n.t(ERROR_KEYS[message] ?? "error.generic");
}

export function notifyActivity() {
	window.dispatchEvent(new Event(ACTIVITY_EVENT));
}

export function authHeaders() {
	const token = localStorage.getItem(TOKEN_KEY);
	return token ? { Authorization: `Bearer ${token}` } : {};
}

export function endSession() {
	localStorage.removeItem(TOKEN_KEY);
	window.location.assign("/login?session=expired");
}

function expireOn401(response) {
	if (response.status === 401) {
		endSession();
		throw new Error(i18n.t("error.sessionExpired"));
	}
}

async function request(endpoint, options) {
	try {
		return await fetch(`${API_URL}${endpoint}`, options);
	}
	catch {
		throw new Error(i18n.t("error.network"));
	}
}

export async function apiFetch(endpoint, options = {}) {
	const response = await request(endpoint,
		{ ...options, headers: 
			{
				"Content-Type": "application/json",
				...authHeaders(),
				...options.headers,
			},
		}
	);
	if (!endpoint.startsWith("/api/auth/"))
		expireOn401(response);

	const isJson = response.headers.get("Content-Type")?.includes("application/json");
	const result = isJson ? await response.json() : null;

	if (!result?.success)
		throw new Error(translateError(result?.error));
	if (options.method && options.method !== "GET")
		notifyActivity();
	return result.data;
}

export async function fetchAuthenticatedBlobUrl(endpoint) {
	const response = await request(endpoint, { headers: authHeaders() });
	expireOn401(response);
	if (!response.ok)
		throw new Error(i18n.t("error.generic"));
	const blob = await response.blob();
	return URL.createObjectURL(blob);
}

export async function downloadFile(endpoint, filename) {
	const url = await fetchAuthenticatedBlobUrl(endpoint);
	const link = document.createElement("a");
	link.href = url;
	link.download = filename;
	document.body.appendChild(link);
	link.click();
	link.remove();
	setTimeout(() => URL.revokeObjectURL(url), 1000);
}
