import SuspenseLoader from '../../../components/SuspenseLoader';
import { useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import useAuth from '../../../hooks/useAuth';

export default function OauthSuccess() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { loginInternal } = useAuth();
  const token = searchParams.get('token');
  const redirect = searchParams.get('redirect') || '/app/work-orders';
  const safeRedirect = redirect.startsWith('/app/') ? redirect : '/app/work-orders';

  useEffect(() => {
    const completeLogin = async () => {
      if (!token) {
        navigate('/account/login', { replace: true });
        return;
      }
      await loginInternal(token);
      navigate(safeRedirect, { replace: true });
    };

    completeLogin();
  }, [token, safeRedirect, loginInternal, navigate]);

  return <SuspenseLoader />;
}
