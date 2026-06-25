export const cognitoConfig = {
  region: 'us-east-1',
  userPoolId: 'us-east-1_izeGmxHKS',
  userPoolClientId: '7m6fbcoagk0cj955eqto3kmc6b',
};

export const isCognitoConfigured = () => {
  return ![
    cognitoConfig.userPoolId,
    cognitoConfig.userPoolClientId,
  ].some((value) => value.startsWith('REPLACE_WITH_'));
};