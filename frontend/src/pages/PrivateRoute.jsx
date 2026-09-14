import { useAuth } from "../hooks/useAuth";
import { Navigate } from "react-router-dom";
import { useTranslation } from "react-i18next";

function PrivateRoute ({ children })
{
	const { isAuthen, loading } = useAuth();
	const { t } = useTranslation();

	if (loading)
<<<<<<< HEAD
		return (<p>{t("loading.load")}</p>);
	if (!isAuthen)
		return (<Navigate to="/login"/>);
	return children;
=======
		return (<p>{t("lodading.load")}</p>);
	if (!isAuthen)
		return (<Navigate to="/login"/>);
	return (children);
>>>>>>> D
}

export default PrivateRoute;