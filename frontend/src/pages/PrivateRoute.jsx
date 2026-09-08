import { useAuth } from "../hooks/useAuth";
import { Navigate } from "react-router-dom";
import { useTranslation } from "react-i18next";

function PrivateRoute ({ children })
{
	const { isAuthen, loading } = useAuth();
	const { t } = useTranslation();

	if (loading)
		return (<p>{t("lodading.load")}</p>);
	if (!!isAuthen)
		return (<Navigate to="/login"/>);
	return ({children});
}

export default PrivateRoute;