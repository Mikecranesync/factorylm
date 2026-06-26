import { lazy, Suspense } from 'react';

import SuspenseLoader from 'src/components/SuspenseLoader';

const Loader = (Component) => (props) =>
  (
    <Suspense fallback={<SuspenseLoader />}>
      <Component {...props} />
    </Suspense>
  );

const OauthSuccess = Loader(
  lazy(() => import('../content/pages/Oauth/OauthSuccess'))
);

const OauthFailure = Loader(
  lazy(() => import('../content/pages/Oauth/OauthFailure'))
);

const oauthRoutes = [
  {
    path: 'success',
    element: <OauthSuccess />
  },
  { path: 'failure', element: <OauthFailure /> }
];

export default oauthRoutes;
