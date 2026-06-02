import asyncio
from winsdk.windows.ui.notifications.management import UserNotificationListener
from winsdk.windows.ui.notifications import UserNotificationListenerAccessStatus

async def main():
    listener = UserNotificationListener.get_current()
    status = await listener.request_access_async()
    
    if status != UserNotificationListenerAccessStatus.ALLOWED:
        print("Access to notifications denied!")
        return
        
    print("Access granted! Reading current notifications...")
    notifications = await listener.get_notifications_async(1) # 1 = Toast
    
    for n in notifications:
        try:
            app_info = n.app_info.display_info.display_name
            bindings = n.notification.visual.bindings
            for b in bindings:
                texts = [t.text for t in b.get_text_elements()]
                print(f"App: {app_info} | Text: {texts}")
        except Exception as e:
            print("Error parsing:", e)

if __name__ == "__main__":
    asyncio.run(main())
