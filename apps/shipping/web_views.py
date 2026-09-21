import uuid
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from apps.listings.web_views import get_or_create_seller_user
from apps.orders.models import OrderShipment
from apps.orders.services.cart import get_cart_items_for_request
from apps.shipping.models import TrackingEvent


def seller_shipments_view(request):
    """
    Page 9: Seller Shipments Management (/seller/shipments/)
    Lists orders waiting dispatch, allows consignment generation,
    courier handover (Steadfast / Pathao), and shipping label printing.
    """
    seller = get_or_create_seller_user(request)
    _, _, cart_count = get_cart_items_for_request(request)
    status_filter = request.GET.get("status", "ALL").upper()

    # Handle Courier Dispatch POST
    if request.method == "POST":
        shipment_id = request.POST.get("shipment_id")
        courier_name = request.POST.get("courier_name", "Steadfast Courier").strip()
        custom_tracking = request.POST.get("tracking_number", "").strip()

        shipment = get_object_or_404(OrderShipment, id=shipment_id, seller=seller)
        tracking_num = custom_tracking or f"EB-{uuid.uuid4().hex[:8].upper()}"
        
        shipment.courier_name = courier_name
        shipment.tracking_number = tracking_num
        shipment.status = OrderShipment.ShipmentStatus.IN_TRANSIT
        shipment.save(update_fields=["courier_name", "tracking_number", "status"])

        TrackingEvent.objects.create(
            shipment=shipment,
            event_name="Dispatched by Seller to Courier",
            location="Seller Hub (Dhaka)",
        )
        return redirect("seller_shipments")

    shipments = OrderShipment.objects.filter(seller=seller).select_related("order").prefetch_related("items__listing__book")

    if status_filter != "ALL":
        shipments = shipments.filter(status=status_filter)

    waiting_count = OrderShipment.objects.filter(seller=seller, status=OrderShipment.ShipmentStatus.WAITING_SELLER).count()
    in_transit_count = OrderShipment.objects.filter(seller=seller, status=OrderShipment.ShipmentStatus.IN_TRANSIT).count()
    delivered_count = OrderShipment.objects.filter(seller=seller, status=OrderShipment.ShipmentStatus.DELIVERED).count()

    return render(
        request,
        "shipping/seller_shipments.html",
        {
            "shipments": shipments,
            "current_status": status_filter,
            "waiting_count": waiting_count,
            "in_transit_count": in_transit_count,
            "delivered_count": delivered_count,
            "cart_count": cart_count,
        },
    )


def parcel_tracking_view(request, tracking_number=None):
    """
    Page 10: Order / Parcel Tracking (/tracking/ & /tracking/<tracking_number>/)
    Public customer parcel tracking page with live status checkpoints and courier details.
    """
    query = (tracking_number or request.GET.get("q", "")).strip()
    shipment = None
    tracking_events = []
    _, _, cart_count = get_cart_items_for_request(request)

    if query:
        shipment = OrderShipment.objects.filter(
            Q(tracking_number__iexact=query) | Q(order__id__istartswith=query)
        ).select_related("order", "seller").prefetch_related("items__listing__book", "tracking_events").first()

        if shipment:
            tracking_events = shipment.tracking_events.all().order_by("timestamp")
            if not tracking_events.exists():
                TrackingEvent.objects.create(
                    shipment=shipment,
                    event_name="Order Placed & Processing",
                    location="Online Bookshop Gateway",
                )
                if shipment.status in [OrderShipment.ShipmentStatus.IN_TRANSIT, OrderShipment.ShipmentStatus.DELIVERED]:
                    TrackingEvent.objects.create(
                        shipment=shipment,
                        event_name="Handed over to Courier",
                        location=f"{shipment.courier_name or 'Steadfast'} Central Hub",
                    )
                if shipment.status == OrderShipment.ShipmentStatus.DELIVERED:
                    TrackingEvent.objects.create(
                        shipment=shipment,
                        event_name="Delivered to Buyer",
                        location="Destination Address",
                    )
                tracking_events = shipment.tracking_events.all().order_by("timestamp")

    return render(
        request,
        "shipping/tracking.html",
        {
            "query": query,
            "shipment": shipment,
            "tracking_events": tracking_events,
            "cart_count": cart_count,
        },
    )
