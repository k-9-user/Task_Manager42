import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "../hooks/useAuth";
import { apiFetch } from "../services/api";

function AdminRoute ({ children })
{
	const { isAuthen, loading: authLoading } = useAuth();
	const { t } = useTranslation();
	const [isAdmin, setIsAdmin] = useState(null);

	useEffect(() =>
	{
		if (!isAuthen)
		{
			setIsAdmin(false);
			return ;
		}
		let cancelled = false;
		apiFetch("/api/users/me")
			.then((data) => { if (!cancelled) setIsAdmin(data.user.role === "admin"); })
			.catch(() => { if (!cancelled) setIsAdmin(false); });
		return () => { cancelled = true; };
	}, [isAuthen]);

	if (authLoading || (isAuthen && isAdmin === null))
		return (<p>{t("loading.load")}</p>);
	if (!isAuthen)
		return (<Navigate to="/login"/>);
	if (!isAdmin)
		return (<Navigate to="/projects"/>);
	return (children);
}

export default AdminRoute;
