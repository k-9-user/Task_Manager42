import { apiFetch } from "./api";

export function getMyProgress()
{
	return apiFetch("/api/gamification/me");
}
