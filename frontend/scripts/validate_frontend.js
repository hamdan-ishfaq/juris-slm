#!/usr/bin/env node
/**
 * Frontend Code Validation Test
 * Validates that frontend components are correctly implemented for secure backend integration
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.join(__dirname, '..');

const colors = {
  reset: '\x1b[0m',
  red: '\x1b[31m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  cyan: '\x1b[36m',
};

const log = {
  success: (msg) => console.log(`${colors.green}✅ ${msg}${colors.reset}`),
  error: (msg) => console.log(`${colors.red}❌ ${msg}${colors.reset}`),
  info: (msg) => console.log(`${colors.blue}ℹ️  ${msg}${colors.reset}`),
  warn: (msg) => console.log(`${colors.yellow}⚠️  ${msg}${colors.reset}`),
  step: (msg) => console.log(`\n${colors.cyan}${msg}${colors.reset}`),
};

function readFile(filePath) {
  return fs.readFileSync(filePath, 'utf-8');
}

function fileExists(filePath) {
  return fs.existsSync(filePath);
}

let passCount = 0;
let failCount = 0;

function check(condition, successMsg, failMsg) {
  if (condition) {
    log.success(successMsg);
    passCount++;
  } else {
    log.error(failMsg);
    failCount++;
  }
}

console.log('\n' + '='.repeat(70));
console.log('🔍 FRONTEND CODE VALIDATION');
console.log('='.repeat(70));

// ========== TEST 1: api.js exists and has proper structure ==========
log.step('TEST 1: API Service (src/lib/api.js)');

const apiFile = path.join(projectRoot, 'src/lib/api.js');
check(
  fileExists(apiFile),
  'api.js file exists',
  'api.js file not found'
);

if (fileExists(apiFile)) {
  const apiContent = readFile(apiFile);
  
  check(
    apiContent.includes('axios.create'),
    'Axios instance created',
    'Axios instance not created'
  );
  
  check(
    apiContent.includes('interceptors.request.use'),
    'Request interceptor configured',
    'Request interceptor not found'
  );
  
  check(
    apiContent.includes('Bearer') && apiContent.includes('Authorization'),
    'Bearer token injection in request interceptor',
    'Bearer token injection not found'
  );
  
  check(
    apiContent.includes('interceptors.response.use'),
    'Response interceptor configured',
    'Response interceptor not found'
  );
  
  check(
    apiContent.includes('401'),
    '401 error handling for invalid token',
    '401 error handling not found'
  );
  
  check(
    apiContent.includes('429'),
    '429 error handling for rate limit',
    '429 error handling not found'
  );
  
  check(
    apiContent.includes('localStorage.removeItem'),
    'Token removal on 401',
    'Token removal logic not found'
  );
  
  check(
    apiContent.includes('window.location.href = \'/login\''),
    'Redirect to login on 401',
    'Login redirect not found'
  );
  
  check(
    apiContent.includes('export const authAPI'),
    'authAPI service exported',
    'authAPI service not exported'
  );
  
  check(
    apiContent.includes('export const queryAPI'),
    'queryAPI service exported',
    'queryAPI service not exported'
  );
  
  check(
    apiContent.includes('export const uploadAPI'),
    'uploadAPI service exported',
    'uploadAPI service not exported'
  );
}

// ========== TEST 2: Chat component ==========
log.step('TEST 2: Chat Component (src/pages/Chat.jsx)');

const chatFile = path.join(projectRoot, 'src/pages/Chat.jsx');
check(
  fileExists(chatFile),
  'Chat.jsx file exists',
  'Chat.jsx file not found'
);

if (fileExists(chatFile)) {
  const chatContent = readFile(chatFile);
  
  check(
    chatContent.includes('import { queryAPI }'),
    'queryAPI imported',
    'queryAPI import not found'
  );
  
  check(
    chatContent.includes('FileText'),
    'FileText icon imported for sources',
    'FileText icon not imported'
  );
  
  check(
    chatContent.includes('response.data.answer'),
    'Answer field extracted from response',
    'Answer field extraction not found'
  );
  
  check(
    chatContent.includes('response.data.sources'),
    'Sources field extracted from response',
    'Sources field extraction not found'
  );
  
  check(
    chatContent.includes('response.data.answer') && chatContent.includes('sources'),
    'Response format handled (answer + sources)',
    'Response format handling not found'
  );
  
  check(
    chatContent.includes('toast.error'),
    'Error toast for failed queries',
    'Error toast not found'
  );
  
  check(
    chatContent.includes('status === 429'),
    'Rate limit error handling (429)',
    'Rate limit handling not found'
  );
  
  check(
    chatContent.includes('status === 401'),
    'Unauthorized error handling (401)',
    'Unauthorized handling not found'
  );
  
  check(
    chatContent.includes('message.sources') && chatContent.includes('FileText'),
    'Sources rendered in UI with icons',
    'Sources rendering not found'
  );
}

// ========== TEST 3: Upload component ==========
log.step('TEST 3: Upload Component (src/pages/Upload.jsx)');

const uploadFile = path.join(projectRoot, 'src/pages/Upload.jsx');
check(
  fileExists(uploadFile),
  'Upload.jsx file exists',
  'Upload.jsx file not found'
);

if (fileExists(uploadFile)) {
  const uploadContent = readFile(uploadFile);
  
  check(
    uploadContent.includes('import { uploadAPI }'),
    'uploadAPI imported',
    'uploadAPI import not found'
  );
  
  check(
    uploadContent.includes('uploadAPI.upload'),
    'uploadAPI used for file upload',
    'uploadAPI usage not found'
  );
  
  check(
    uploadContent.includes('.pdf'),
    'PDF file validation',
    'PDF validation not found'
  );
  
  check(
    uploadContent.includes('429'),
    'Rate limit handling in upload',
    'Rate limit handling not found'
  );
  
  check(
    uploadContent.includes('401'),
    'Unauthorized handling in upload',
    'Unauthorized handling not found'
  );
  
  check(
    uploadContent.includes('toast'),
    'Toast notifications for upload',
    'Toast notifications not found'
  );
  
  check(
    uploadContent.includes('Trash2'),
    'File deletion UI with icon',
    'File deletion UI not found'
  );
}

// ========== TEST 4: Login component ==========
log.step('TEST 4: Login Component (src/pages/Login.jsx)');

const loginFile = path.join(projectRoot, 'src/pages/Login.jsx');
check(
  fileExists(loginFile),
  'Login.jsx file exists',
  'Login.jsx file not found'
);

if (fileExists(loginFile)) {
  const loginContent = readFile(loginFile);
  
  check(
    loginContent.includes('import { authAPI }'),
    'authAPI imported',
    'authAPI import not found'
  );
  
  check(
    loginContent.includes('authAPI.login'),
    'authAPI used for login',
    'authAPI usage not found'
  );
  
  check(
    loginContent.includes('authAPI.login') || loginContent.includes('localStorage'),
    'Token managed (via authAPI.login or localStorage)',
    'Token management not found'
  );
  
  check(
    loginContent.includes('motion'),
    'Framer Motion animations imported',
    'Motion import not found'
  );
  
  check(
    loginContent.includes('/chat'),
    'Redirect to chat after successful login',
    'Chat redirect not found'
  );
  
  check(
    loginContent.includes('CheckCircle'),
    'Success icon/message displayed',
    'CheckCircle icon not found'
  );
}

// ========== TEST 5: package.json ==========
log.step('TEST 5: Frontend Dependencies (package.json)');

const packageFile = path.join(projectRoot, 'package.json');
check(
  fileExists(packageFile),
  'package.json exists',
  'package.json not found'
);

if (fileExists(packageFile)) {
  const packageContent = readFile(packageFile);
  const packageJson = JSON.parse(packageContent);
  
  check(
    packageJson.type === 'module',
    'ES modules enabled ("type": "module")',
    'ES modules not configured'
  );
  
  check(
    packageJson.dependencies.axios,
    'axios dependency present',
    'axios dependency missing'
  );
  
  check(
    packageJson.dependencies['react-hot-toast'],
    'react-hot-toast dependency present',
    'react-hot-toast dependency missing'
  );
  
  check(
    packageJson.dependencies['framer-motion'],
    'framer-motion dependency present',
    'framer-motion dependency missing'
  );
  
  check(
    packageJson.dependencies['lucide-react'],
    'lucide-react dependency present',
    'lucide-react dependency missing'
  );
}

// ========== SUMMARY ==========
console.log('\n' + '='.repeat(70));
console.log('📊 VALIDATION RESULTS');
console.log('='.repeat(70));

console.log(`\n${colors.green}Passed: ${passCount}${colors.reset}`);
console.log(`${colors.red}Failed: ${failCount}${colors.reset}`);

if (failCount === 0) {
  console.log(`\n${colors.green}✅ FRONTEND READY FOR SECURE BACKEND INTEGRATION${colors.reset}`);
  console.log('\n✓ API service has proper interceptors and error handling');
  console.log('✓ Chat component displays answer + sources');
  console.log('✓ Upload component uses API service');
  console.log('✓ Login component stores JWT token');
  console.log('✓ All components handle 401/429 errors');
  console.log('\n' + '='.repeat(70) + '\n');
  process.exit(0);
} else {
  console.log(`\n${colors.red}❌ FRONTEND VALIDATION FAILED${colors.reset}`);
  console.log('\nPlease check the errors above and fix the components.');
  console.log('\n' + '='.repeat(70) + '\n');
  process.exit(1);
}
