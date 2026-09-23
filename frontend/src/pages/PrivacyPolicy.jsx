import { Fragment, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useLocation } from 'react-router-dom';
import './PrivacyPolicy.css';

const SECTIONS = ["collect", "use", "sharing", "security", "retention"];
const RIGHTS = ["access", "rectification", "erasure", "objection"];

function PrivacyPolicy ()
{
	const { t } = useTranslation();
	const { hash } = useLocation();

	useEffect(() => {
		if (hash)
			document.getElementById(hash.slice(1))?.scrollIntoView();
	}, [hash]);

	return (
		<div className="legal-page">
			<h1>{t("legal.privacy.title")}</h1>
			<p><em>{t("legal.privacy.updated")}</em></p>
			{SECTIONS.map((section) => (
				<Fragment key={section}>
					<h2>{t(`legal.privacy.sections.${section}.title`)}</h2>
					<p>{t(`legal.privacy.sections.${section}.body`)}</p>
				</Fragment>
			))}
			<h2 id="your-rights">{t("legal.privacy.rights.title")}</h2>
			<p>{t("legal.privacy.rights.intro")}</p>
			<ul className="legal-rights">
				{RIGHTS.map((right) => (
					<li key={right}>{t(`legal.privacy.rights.items.${right}`)}</li>
				))}
			</ul>
			<p>{t("legal.privacy.rights.footer")}</p>
			<h2 id="account-deletion">{t("legal.privacy.deletion.title")}</h2>
			<p>{t("legal.privacy.deletion.body")}</p>
			<h2>{t("legal.privacy.contactTitle")}</h2>
			<p>{t("legal.privacy.contactBody")}</p>
		</div>
	);
}

export default PrivacyPolicy;
