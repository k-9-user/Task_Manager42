import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { isLoggedIn } from "../services/authService";
import { getMe } from "../services/userservice";

function AdminRoute ({ children })
{
	const loggedIn = isLoggedIn();
	const { t } = useTranslation();
	const [isAdmin, setIsAdmin] = useState(null);

	useEffect(() =>
	{
		if (!loggedIn)
			return ;
		let cancelled = false;
		getMe()
			.then((data) => { if (!cancelled) setIsAdmin(data.user.role === "admin"); })
			.catch(() => { if (!cancelled) setIsAdmin(false); });
		return () => { cancelled = true; };
	}, [loggedIn]);

	if (!loggedIn)
		return (<Navigate to="/login"/>);
	if (isAdmin === null)
		return (<p>{t("loading.load")}</p>);
	if (!isAdmin)
		return (<Navigate to="/projects"/>);
	return (children);
}

export default AdminRoute;
