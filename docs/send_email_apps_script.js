/*
 * Real Estate AVM: sends the "forgot password" code from your Gmail. Free.
 *
 * Setup (once, about 5 minutes):
 * 1. Go to https://script.google.com and click "New project".
 * 2. Delete what is there and paste this whole file. Click Save.
 * 3. Click Project Settings (gear icon) > Script properties > Add script property:
 *      Property: SECRET    Value: a long random word (use the same one on Render)
 *    Click Save script properties.
 * 4. Click Deploy > New deployment > the gear next to "Select type" > Web app.
 *      Execute as: Me
 *      Who has access: Anyone
 *    Click Deploy, then Authorize access and allow it with your Google account.
 *    (Google may say the app is not verified: click Advanced > Go to project.)
 * 5. Copy the Web app URL (it ends in /exec).
 * 6. On Render > real-estate-avm-api > Environment, add:
 *      MAIL_SCRIPT_URL     the Web app URL
 *      MAIL_SCRIPT_SECRET  the same random word as in step 3
 *
 * Only someone with the secret can make it send an email.
 */

function doPost(e) {
  var data;
  try {
    data = JSON.parse(e.postData.contents);
  } catch (err) {
    return reply('bad request');
  }
  var secret = PropertiesService.getScriptProperties().getProperty('SECRET');
  if (!secret || data.secret !== secret) {
    return reply('wrong secret');
  }
  if (!data.to || !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(data.to)) {
    return reply('bad email');
  }
  MailApp.sendEmail({
    to: data.to,
    subject: String(data.subject || 'Your Real Estate AVM code'),
    body: String(data.text || ''),
    htmlBody: String(data.html || data.text || ''),
    name: 'Real Estate AVM',
  });
  return reply('ok');
}

function reply(text) {
  return ContentService.createTextOutput(text).setMimeType(ContentService.MimeType.TEXT);
}
