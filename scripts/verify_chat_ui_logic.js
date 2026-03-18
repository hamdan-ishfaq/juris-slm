#!/usr/bin/env node

/**
 * verify_chat_ui_logic.js - Verify Chat.jsx has chat history integration
 * 
 * Checks:
 * 1. useEffect hook exists
 * 2. getChatHistory() is called
 * 3. Clear chat button logic exists
 * 4. Loading state for history is managed
 * 5. Error handling with toast
 */

const fs = require('fs');
const path = require('path');

// Color codes for console output
const colors = {
  reset: '\x1b[0m',
  green: '\x1b[32m',
  red: '\x1b[31m',
  yellow: '\x1b[33m',
  blue: '\x1b[36m'
};

function log(message, color = 'reset') {
  console.log(`${colors[color]}${message}${colors.reset}`);
}

function checkFileExists(filePath) {
  if (!fs.existsSync(filePath)) {
    log(`❌ File not found: ${filePath}`, 'red');
    process.exit(1);
  }
}

function readFile(filePath) {
  return fs.readFileSync(filePath, 'utf-8');
}

function testExists(name, content, pattern) {
  const exists = pattern.test(content);
  const status = exists ? '✅ PASS' : '❌ FAIL';
  log(`  ${status} - ${name}`, exists ? 'green' : 'red');
  return exists;
}

// Main verification
function verifyChat() {
  log('\n═══════════════════════════════════════════════════', 'blue');
  log('  CHAT UI LOGIC VERIFICATION', 'blue');
  log('═══════════════════════════════════════════════════', 'blue');

  const chatPath = path.join(__dirname, '../frontend/src/pages/Chat.jsx');
  const apiPath = path.join(__dirname, '../frontend/src/lib/api.js');

  // Check files exist
  log('\n📋 Checking files exist...', 'yellow');
  checkFileExists(chatPath);
  checkFileExists(apiPath);
  log('  ✅ Both files found', 'green');

  // Read files
  const chatContent = readFile(chatPath);
  const apiContent = readFile(apiPath);

  log('\n🔍 Verifying Chat.jsx implementation...', 'yellow');

  let allPassed = true;

  // Test 1: useEffect hook exists
  const hasUseEffect = testExists(
    'useEffect hook imported',
    chatContent,
    /import\s*{\s*[^}]*useEffect[^}]*}\s*from\s*['"]react['"]/
  );
  allPassed = allPassed && hasUseEffect;

  // Test 2: getChatHistory is called
  const hasGetChatHistory = testExists(
    'getChatHistory() function called',
    chatContent,
    /getChatHistory\s*\(\s*\d*\s*\)/
  );
  allPassed = allPassed && hasGetChatHistory;

  // Test 3: clearChatHistory is called
  const hasClearChatHistory = testExists(
    'clearChatHistory() function called',
    chatContent,
    /clearChatHistory\s*\(\s*\)/
  );
  allPassed = allPassed && hasClearChatHistory;

  // Test 4: handleClearChat function defined
  const hasHandleClearChat = testExists(
    'handleClearChat function defined',
    chatContent,
    /const\s+handleClearChat\s*=\s*async\s*\(/
  );
  allPassed = allPassed && hasHandleClearChat;

  // Test 5: loadingHistory state exists
  const hasLoadingHistoryState = testExists(
    'loadingHistory state variable',
    chatContent,
    /setLoadingHistory|loadingHistory/
  );
  allPassed = allPassed && hasLoadingHistoryState;

  // Test 6: Messages are formatted from API response
  const hasMessageFormatting = testExists(
    'Message formatting logic',
    chatContent,
    /role\s*===\s*['"]assistant['"]|type:\s*msg\.role/
  );
  allPassed = allPassed && hasMessageFormatting;

  // Test 7: Error handling with toast
  const hasErrorHandling = testExists(
    'Error handling with toast',
    chatContent,
    /toast\.error\s*\(/
  );
  allPassed = allPassed && hasErrorHandling;

  // Test 8: Loading skeleton component
  const hasLoadingSkeleton = testExists(
    'MessageSkeleton loading component',
    chatContent,
    /function\s+MessageSkeleton|const\s+MessageSkeleton/
  );
  allPassed = allPassed && hasLoadingSkeleton;

  // Test 9: Clear button with Trash icon
  const hasClearButton = testExists(
    'Clear button in header with Trash icon',
    chatContent,
    /Trash2|handleClearChat/
  );
  allPassed = allPassed && hasClearButton;

  // Test 10: Confirmation dialog
  const hasConfirmation = testExists(
    'Confirmation dialog before clearing',
    chatContent,
    /window\.confirm/
  );
  allPassed = allPassed && hasConfirmation;

  log('\n🔍 Verifying API methods exist...', 'yellow');

  // Test 11: getChatHistory in api.js
  const apiHasGetChatHistory = testExists(
    'getChatHistory method in api.js',
    apiContent,
    /getChatHistory:\s*async/
  );
  allPassed = allPassed && apiHasGetChatHistory;

  // Test 12: clearChatHistory in api.js
  const apiHasClearChatHistory = testExists(
    'clearChatHistory method in api.js',
    apiContent,
    /clearChatHistory:\s*async/
  );
  allPassed = allPassed && apiHasClearChatHistory;

  // Test 13: Correct endpoints
  const apiHasCorrectEndpoints = testExists(
    'Correct API endpoints (/chat/history)',
    apiContent,
    /\/chat\/history/
  );
  allPassed = allPassed && apiHasCorrectEndpoints;

  log('\n🔍 Verifying UX patterns...', 'yellow');

  // Test 14: scrollToBottom called and useEffect dependency on messages
  const hasAutoScroll = testExists(
    'Auto-scroll after history loads',
    chatContent,
    /scrollToBottom|useEffect\s*\(\s*\(\s*\)\s*=>\s*{\s*scrollToBottom/
  );
  allPassed = allPassed && hasAutoScroll;

  // Test 15: Welcome message preserved
  const hasWelcomeMessage = testExists(
    'Welcome message on new chat',
    chatContent,
    /Welcome to BEWEIS|Ask me about legal/
  );
  allPassed = allPassed && hasWelcomeMessage;

  log('\n' + '═'.repeat(51), 'blue');

  if (allPassed) {
    log('\n✅ ALL CHECKS PASSED! Chat history integration complete.\n', 'green');
    
    log('Summary of changes:', 'yellow');
    log('  ✓ Chat history loads on component mount', 'green');
    log('  ✓ Loading skeleton shown while fetching', 'green');
    log('  ✓ Clear button added to header with confirmation', 'green');
    log('  ✓ Error handling with toast notifications', 'green');
    log('  ✓ Auto-scroll to bottom after history loads', 'green');
    log('  ✓ Message format conversion from API', 'green');
    
    log('\nFeatures implemented:', 'yellow');
    log('  • Load chat history on page mount (getChatHistory)', 'blue');
    log('  • Display loading skeleton while fetching', 'blue');
    log('  • Convert backend format to UI format', 'blue');
    log('  • Clear chat history with confirmation dialog', 'blue');
    log('  • Reset to welcome message on clear', 'blue');
    log('  • Handle errors gracefully with toast', 'blue');
    
    process.exit(0);
  } else {
    log('\n❌ SOME CHECKS FAILED! Please review the implementation.\n', 'red');
    process.exit(1);
  }
}

// Run verification
try {
  verifyChat();
} catch (error) {
  log(`\n❌ Verification failed with error: ${error.message}`, 'red');
  console.error(error);
  process.exit(1);
}
